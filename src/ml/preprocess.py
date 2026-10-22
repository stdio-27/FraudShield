import json
import logging
import os

import joblib
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

try:
    from .features import FEATURE_COLUMNS, engineer_features
    from .dataset import resolve_dataset_path
except ImportError:  # executed as a plain script: python src/ml/preprocess.py
    from features import FEATURE_COLUMNS, engineer_features
    from dataset import resolve_dataset_path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def preprocess_data(data_path: str, models_dir: str):
    """Loads, splits, engineers, scales, and resamples the data."""
    logging.info(f"Loading data from {data_path}...")
    raw = pd.read_csv(data_path)
    y_all = raw["Class"]

    logging.info(f"Initial class distribution:\n{y_all.value_counts()}")

    # Split the RAW data first so that every statistic below (amount z-score
    # parameters, scaler) is learned from the training split only.
    logging.info("Performing 70/15/15 stratified split...")
    raw_train, raw_temp, y_train, y_temp = train_test_split(
        raw, y_all, test_size=0.30, stratify=y_all, random_state=42
    )
    raw_val, raw_test, y_val, y_test = train_test_split(
        raw_temp, y_temp, test_size=0.50, stratify=y_temp, random_state=42
    )

    amount_mean = float(raw_train["Amount"].mean())
    amount_std = float(raw_train["Amount"].std())

    X_train = engineer_features(raw_train, amount_mean, amount_std)
    X_val = engineer_features(raw_val, amount_mean, amount_std)
    X_test = engineer_features(raw_test, amount_mean, amount_std)

    logging.info(f"Train shape: X={X_train.shape}, y={y_train.shape}")
    logging.info(f"Val shape:   X={X_val.shape}, y={y_val.shape}")
    logging.info(f"Test shape:  X={X_test.shape}, y={y_test.shape}")

    logging.info("Fitting StandardScaler on training set only...")
    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train), columns=FEATURE_COLUMNS)
    X_val_scaled = pd.DataFrame(scaler.transform(X_val), columns=FEATURE_COLUMNS)
    X_test_scaled = pd.DataFrame(scaler.transform(X_test), columns=FEATURE_COLUMNS)

    os.makedirs(models_dir, exist_ok=True)
    scaler_path = os.path.join(models_dir, "scaler.joblib")
    joblib.dump(scaler, scaler_path)
    logging.info(f"Saved fitted scaler to {scaler_path}")

    stats_path = os.path.join(models_dir, "amount_stats.json")
    with open(stats_path, "w") as f:
        json.dump({"mean": amount_mean, "std": amount_std}, f, indent=2)
    logging.info(f"Saved amount stats (mean={amount_mean:.4f}, std={amount_std:.4f}) to {stats_path}")

    logging.info("Applying SMOTE to the training set...")
    smote = SMOTE(random_state=42)
    X_train_resampled, y_train_resampled = smote.fit_resample(X_train_scaled, y_train.reset_index(drop=True))

    logging.info(f"Shape before SMOTE: {X_train_scaled.shape}")
    logging.info(f"Shape after SMOTE: {X_train_resampled.shape}")
    logging.info(f"Class distribution after SMOTE:\n{y_train_resampled.value_counts()}")

    return (
        (X_train_resampled, y_train_resampled),
        (X_val_scaled, y_val.reset_index(drop=True)),
        (X_test_scaled, y_test.reset_index(drop=True)),
    )


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_path = resolve_dataset_path()
    if not data_path:
        raise SystemExit("creditcard.csv not found. Set DATASET_PATH or place it in data/.")
    preprocess_data(data_path, os.path.join(base_dir, "models"))
