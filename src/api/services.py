import hashlib
import json
import logging
import os
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

from ..ml.features import FEATURE_COLUMNS, engineer_features

logger = logging.getLogger(__name__)

MODEL_FILE = "xgboost_fraud_model.json"
SCALER_FILE = "scaler.joblib"
STATS_FILE = "amount_stats.json"
MANIFEST_FILE = "feature_manifest.json"

DEFAULT_THRESHOLD = 0.5


@dataclass
class ScoreResult:
    fraud_score: float
    is_flagged: bool
    decision: str
    shap_reasons: Optional[List[Dict[str, Any]]]
    hour_of_day: int
    amount_zscore: float


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ModelManager:
    """Singleton holding the ML artifacts so they are loaded once, not per request."""

    _instance = None

    # Training-set Amount statistics used only when amount_stats.json is missing.
    FALLBACK_AMOUNT_MEAN = 88.3496
    FALLBACK_AMOUNT_STD = 250.1201

    def __new__(cls):
        if cls._instance is None:
            inst = super().__new__(cls)
            inst.model = None
            inst.explainer = None
            inst.scaler = None
            inst.amount_mean = cls.FALLBACK_AMOUNT_MEAN
            inst.amount_std = cls.FALLBACK_AMOUNT_STD
            inst.threshold = DEFAULT_THRESHOLD
            inst.load_error = None
            inst._ready = False
            inst._load_lock = threading.Lock()
            inst._infer_lock = threading.Lock()
            cls._instance = inst
        return cls._instance

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------ loading
    def load_artifacts(self, models_dir: str) -> None:
        """Load and cross-validate every artifact.  Raises on any inconsistency."""
        with self._load_lock:
            if self._ready:
                return
            try:
                self._load(models_dir)
            except Exception as exc:
                self.load_error = str(exc)
                self._ready = False
                raise
            self.load_error = None
            self._ready = True

    def _load(self, models_dir: str) -> None:
        model_path = os.path.join(models_dir, MODEL_FILE)
        scaler_path = os.path.join(models_dir, SCALER_FILE)
        for path in (model_path, scaler_path):
            if not os.path.isfile(path):
                raise FileNotFoundError(f"Missing model artifact: {path}. Run `python -m src.ml.train`.")

        manifest = self._read_manifest(models_dir)
        stats_path = os.path.join(models_dir, STATS_FILE)
        if manifest and "artifacts" in manifest:
            self._verify_hashes(models_dir, manifest["artifacts"])
        else:
            logger.warning("No %s found; skipping artifact integrity check.", MANIFEST_FILE)

        if manifest and manifest.get("feature_columns") not in (None, FEATURE_COLUMNS):
            raise RuntimeError("feature_manifest.json feature_columns do not match the serving code.")

        logger.info("Loading XGBoost model...")
        model = xgb.XGBClassifier()
        model.load_model(model_path)

        logger.info("Loading scaler...")
        scaler = joblib.load(scaler_path)

        n_features = len(FEATURE_COLUMNS)
        scaler_features = getattr(scaler, "n_features_in_", None)
        if scaler_features != n_features:
            raise RuntimeError(
                f"Scaler was fitted on {scaler_features} features but the serving pipeline "
                f"produces {n_features}. The artifacts are stale or from a different pipeline; "
                "retrain with `python -m src.ml.train`."
            )
        scaler_names = getattr(scaler, "feature_names_in_", None)
        if scaler_names is not None and list(scaler_names) != FEATURE_COLUMNS:
            raise RuntimeError("Scaler feature names/order differ from FEATURE_COLUMNS; retrain the model.")

        model_features = self._model_feature_count(model)
        if model_features is not None and model_features != n_features:
            raise RuntimeError(
                f"Model expects {model_features} features but the serving pipeline produces {n_features}."
            )

        if os.path.isfile(stats_path):
            with open(stats_path, "r") as f:
                stats = json.load(f)
            self.amount_mean, self.amount_std = float(stats["mean"]), float(stats["std"])
            logger.info("Loaded amount stats: mean=%s, std=%s", self.amount_mean, self.amount_std)
        else:
            self.amount_mean = self.FALLBACK_AMOUNT_MEAN
            self.amount_std = self.FALLBACK_AMOUNT_STD
            logger.warning("%s not found; using fallback amount statistics.", STATS_FILE)

        self.threshold = self._resolve_threshold(manifest)
        logger.info("Decision threshold: %.4f", self.threshold)

        self.model = model
        self.scaler = scaler
        self.explainer = self._build_explainer(model)
        logger.info("All model artifacts loaded successfully.")

    @staticmethod
    def _read_manifest(models_dir: str) -> Optional[dict]:
        path = os.path.join(models_dir, MANIFEST_FILE)
        if not os.path.isfile(path):
            return None
        with open(path, "r") as f:
            return json.load(f)

    @staticmethod
    def _verify_hashes(models_dir: str, expected: Dict[str, str]) -> None:
        for name, digest in expected.items():
            path = os.path.join(models_dir, name)
            if not os.path.isfile(path):
                raise RuntimeError(f"Manifest lists {name} but the file is missing.")
            if _sha256(path) != digest:
                raise RuntimeError(
                    f"Integrity check failed for {name}: it does not match feature_manifest.json "
                    "(artifacts were modified or are from different training runs)."
                )

    @staticmethod
    def _model_feature_count(model: xgb.XGBClassifier) -> Optional[int]:
        try:
            return int(model.get_booster().num_features())
        except Exception:
            return None

    @staticmethod
    def _resolve_threshold(manifest: Optional[dict]) -> float:
        env_value = os.getenv("DECISION_THRESHOLD") or os.getenv("DEFAULT_THRESHOLD")
        if env_value:
            try:
                value = float(env_value)
                if 0.0 < value < 1.0:
                    return value
                logger.warning("Ignoring out-of-range DECISION_THRESHOLD=%s", env_value)
            except ValueError:
                logger.warning("Ignoring non-numeric DECISION_THRESHOLD=%s", env_value)
        if manifest and manifest.get("decision_threshold") is not None:
            return float(manifest["decision_threshold"])
        return DEFAULT_THRESHOLD

    @staticmethod
    def _build_explainer(model: xgb.XGBClassifier):
        """Rebuilt from the model (no pickle).  Scoring still works without SHAP."""
        try:
            import shap

            return shap.TreeExplainer(model)
        except Exception as exc:
            logger.error("SHAP explainer unavailable; explanations disabled: %s", exc)
            return None

    # --------------------------------------------------------------- inference
    def engineer_features(self, raw: pd.DataFrame) -> pd.DataFrame:
        return engineer_features(raw, self.amount_mean, self.amount_std)

    @staticmethod
    def frame_from_request(req_data: dict) -> pd.DataFrame:
        row = {"Time": req_data["time_seconds"], "Amount": req_data["amount"]}
        for i in range(1, 29):
            row[f"V{i}"] = req_data[f"v{i}"]
        return pd.DataFrame([row])

    def score(self, req_data: dict) -> ScoreResult:
        """Score a single request payload (keys: amount, time_seconds, v1..v28)."""
        return self.score_frame(self.frame_from_request(req_data))[0]

    def score_frame(self, raw: pd.DataFrame) -> List[ScoreResult]:
        """
        Score a raw frame with ``Time``, ``Amount`` and ``V1``..``V28`` columns.
        Blocking and CPU-bound: call it from a worker thread, never the event loop.
        """
        if not self._ready:
            raise RuntimeError("Model artifacts are not loaded.")

        features = self.engineer_features(raw)
        with self._infer_lock:
            scaled = pd.DataFrame(self.scaler.transform(features), columns=FEATURE_COLUMNS)
            probas = self.model.predict_proba(scaled)[:, 1]
            flagged_idx = [i for i, p in enumerate(probas) if p >= self.threshold]
            reasons = self._explain(scaled, flagged_idx)

        results = []
        for i, proba in enumerate(probas):
            flagged = float(proba) >= self.threshold
            results.append(
                ScoreResult(
                    fraud_score=float(proba),
                    is_flagged=flagged,
                    decision="REVIEW" if flagged else "APPROVE",
                    shap_reasons=reasons.get(i),
                    hour_of_day=int(features["hour_of_day"].iloc[i]),
                    amount_zscore=float(features["amount_zscore"].iloc[i]),
                )
            )
        return results

    def _explain(self, scaled: pd.DataFrame, indices: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        """Top-5 SHAP attributions for the given row indices (only flagged rows pay this cost)."""
        if not indices or self.explainer is None:
            return {}
        try:
            shap_vals = self.explainer.shap_values(scaled.iloc[indices])
            if isinstance(shap_vals, list):
                shap_vals = shap_vals[1]
            shap_vals = np.asarray(shap_vals)
            if shap_vals.ndim == 3:
                shap_vals = shap_vals[:, :, -1]

            out = {}
            for row, idx in enumerate(indices):
                sample = shap_vals[row]
                order = np.argsort(-np.abs(sample))[:5]
                out[idx] = [
                    {
                        "feature": FEATURE_COLUMNS[j],
                        "attribution_score": float(abs(sample[j])),
                        "direction": "INCREASE RISK" if sample[j] > 0 else "DECREASE RISK",
                    }
                    for j in order
                ]
            return out
        except Exception as exc:
            logger.error("SHAP explanation failed; returning score without reasons: %s", exc)
            return {}


model_manager = ModelManager()
