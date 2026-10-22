"""
Training entry point.  Run from the project root:

    python -m src.ml.train

Writes the complete serving artifact set to ``models/``:
    xgboost_fraud_model.json   the model
    scaler.joblib              StandardScaler fitted on FEATURE_COLUMNS
    amount_stats.json          train-split mean/std used for ``amount_zscore``
    feature_manifest.json      feature order, decision threshold, SHA-256 of artifacts
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone

import numpy as np
import xgboost as xgb
from sklearn.metrics import (
    auc,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
)

try:
    from .preprocess import preprocess_data
    from .features import FEATURE_COLUMNS
    from .dataset import resolve_dataset_path
except ImportError:  # executed as a plain script: python src/ml/train.py
    from preprocess import preprocess_data
    from features import FEATURE_COLUMNS
    from dataset import resolve_dataset_path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

MODEL_FILE = "xgboost_fraud_model.json"
SCALER_FILE = "scaler.joblib"
STATS_FILE = "amount_stats.json"
MANIFEST_FILE = "feature_manifest.json"


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _best_f1_threshold(y_true, proba) -> float:
    """Threshold maximising F1 on the validation set (SMOTE-trained scores are not calibrated)."""
    precision, recall, thresholds = precision_recall_curve(y_true, proba)
    # precision/recall have one more entry than thresholds
    f1 = 2 * precision[:-1] * recall[:-1] / np.clip(precision[:-1] + recall[:-1], 1e-12, None)
    if len(f1) == 0:
        return 0.5
    return float(thresholds[int(np.argmax(f1))])


def train_and_evaluate(data_path: str, models_dir: str):
    train_data, val_data, test_data = preprocess_data(data_path, models_dir)
    X_train, y_train = train_data
    X_val, y_val = val_data
    X_test, y_test = test_data

    logging.info("Training XGBoost classifier...")
    # scale_pos_weight=1.0 because SMOTE already balanced the training set
    clf = xgb.XGBClassifier(
        max_depth=6,
        learning_rate=0.05,
        n_estimators=300,
        scale_pos_weight=1.0,
        eval_metric="aucpr",
        random_state=42,
    )
    clf.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=50)

    val_proba = clf.predict_proba(X_val)[:, 1]
    precision_val, recall_val, _ = precision_recall_curve(y_val, val_proba)
    logging.info(f"Validation PR-AUC: {auc(recall_val, precision_val):.4f}")

    threshold = _best_f1_threshold(y_val, val_proba)
    logging.info(f"Decision threshold selected on validation set (max F1): {threshold:.4f}")

    test_proba = clf.predict_proba(X_test)[:, 1]
    test_preds = (test_proba >= threshold).astype(int)
    precision_test, recall_test, _ = precision_recall_curve(y_test, test_proba)
    pr_auc_test = float(auc(recall_test, precision_test))
    logging.info(f"Test PR-AUC: {pr_auc_test:.4f}")
    logging.info("\nTest confusion matrix @ threshold:\n" + str(confusion_matrix(y_test, test_preds)))
    logging.info("\n" + classification_report(y_test, test_preds))

    os.makedirs(models_dir, exist_ok=True)
    model_path = os.path.join(models_dir, MODEL_FILE)
    clf.save_model(model_path)
    logging.info(f"Saved XGBoost model to {model_path}")

    # The SHAP explainer is rebuilt from the model at serving time; no pickle is shipped.
    manifest = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "feature_columns": FEATURE_COLUMNS,
        "decision_threshold": threshold,
        "test_pr_auc": pr_auc_test,
        "artifacts": {
            name: _sha256(os.path.join(models_dir, name))
            for name in (MODEL_FILE, SCALER_FILE, STATS_FILE)
        },
    }
    manifest_path = os.path.join(models_dir, MANIFEST_FILE)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    logging.info(f"Saved feature manifest to {manifest_path}")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_path = resolve_dataset_path()
    if not data_path:
        logging.error(
            "Dataset not found. Place creditcard.csv in data/ (or the project root) "
            "or set DATASET_PATH."
        )
    else:
        train_and_evaluate(data_path, os.path.join(base_dir, "models"))
