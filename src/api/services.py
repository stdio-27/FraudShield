import os
import json
import joblib
import xgboost as xgb
import pandas as pd
import numpy as np
import logging
from typing import List, Tuple, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class ModelManager:
    """Singleton class to manage ML model artifacts to avoid disk I/O on every request."""
    _instance = None

    model: xgb.XGBClassifier = None
    explainer = None
    scaler = None

    # Fallback training set parameters for Amount Z-score.
    # These are overridden at runtime if models/amount_stats.json exists.
    AMOUNT_MEAN = 88.3496
    AMOUNT_STD = 250.1201

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
        return cls._instance

    def load_artifacts(self, models_dir: str):
        """Loads artifacts into memory if not already loaded."""
        if self.model is None:
            logging.info("Loading XGBoost model...")
            self.model = xgb.XGBClassifier()
            self.model.load_model(os.path.join(models_dir, "xgboost_fraud_model.json"))

            logging.info("Loading SHAP Explainer...")
            self.explainer = joblib.load(os.path.join(models_dir, "shap_explainer.pkl"))

            logging.info("Loading Scaler...")
            self.scaler = joblib.load(os.path.join(models_dir, "scaler.joblib"))

            # Load amount stats dynamically if available (fixes hardcoded skew)
            stats_path = os.path.join(models_dir, "amount_stats.json")
            if os.path.exists(stats_path):
                with open(stats_path, "r") as f:
                    stats = json.load(f)
                self.AMOUNT_MEAN = stats["mean"]
                self.AMOUNT_STD = stats["std"]
                logging.info(f"Loaded amount stats: mean={self.AMOUNT_MEAN}, std={self.AMOUNT_STD}")
            else:
                logging.warning(
                    f"amount_stats.json not found in {models_dir}. "
                    f"Using hardcoded fallbacks: mean={self.AMOUNT_MEAN}, std={self.AMOUNT_STD}"
                )

            logging.info("All model artifacts loaded successfully into memory.")

    def engineer_features(self, req_data: dict) -> pd.DataFrame:
        """Transforms raw request into the exact DataFrame features expected by the model."""
        amount = req_data['amount']
        time_sec = req_data['time_seconds']

        feature_dict = {f"V{i}": req_data[f"v{i}"] for i in range(1, 29)}
        feature_dict["Amount"] = amount

        # Derived features
        hour_of_day = (time_sec / 3600) % 24
        # Fix: round before int comparison to avoid floating-point precision bugs
        day_of_week = int(round((time_sec // 86400) % 7))
        is_weekend = int(day_of_week in [5, 6])
        amount_zscore = (amount - self.AMOUNT_MEAN) / self.AMOUNT_STD
        amount_log = np.log1p(amount)
        high_value_flag = int(amount > 1000)

        feature_dict.update({
            "hour_of_day": hour_of_day,
            "is_weekend": is_weekend,
            "amount_zscore": amount_zscore,
            "amount_log": amount_log,
            "high_value_flag": high_value_flag
        })

        # Strict order to match training DataFrame columns
        ordered_cols = [f"V{i}" for i in range(1, 29)] + [
            "Amount", "hour_of_day", "is_weekend",
            "amount_zscore", "amount_log", "high_value_flag"
        ]

        return pd.DataFrame([feature_dict])[ordered_cols]

    def predict(self, req_data: dict, threshold: float = 0.5) -> Tuple[float, bool, str, Any]:
        """Runs the complete inference and explainability pipeline."""
        df_engineered = self.engineer_features(req_data)

        # Scale
        df_scaled = pd.DataFrame(self.scaler.transform(df_engineered), columns=df_engineered.columns)

        # Predict Proba
        probas = self.model.predict_proba(df_scaled)
        fraud_score = float(probas[0, 1])

        is_flagged = fraud_score > threshold
        decision = "REVIEW" if is_flagged else "APPROVE"

        shap_reasons = None
        if is_flagged:
            # SHAP calculation for the single flagged transaction
            shap_vals = self.explainer.shap_values(df_scaled)

            # xgboost binary classification often returns a single array or list of arrays
            if isinstance(shap_vals, list):
                shap_vals = shap_vals[1]  # positive class

            sample_shap = shap_vals[0]

            feature_impacts = []
            for i, col in enumerate(df_scaled.columns):
                val = float(sample_shap[i])
                feature_impacts.append({
                    "feature": col,
                    "score": abs(val),
                    "raw_score": val,
                    "direction": "INCREASE RISK" if val > 0 else "DECREASE RISK"
                })

            # Sort by absolute impact and take top 5
            feature_impacts.sort(key=lambda x: x["score"], reverse=True)
            top_5 = feature_impacts[:5]

            shap_reasons = []
            for item in top_5:
                shap_reasons.append({
                    "feature": item["feature"],
                    "attribution_score": item["score"],
                    "direction": item["direction"]
                })

        return fraud_score, is_flagged, decision, shap_reasons


model_manager = ModelManager()
