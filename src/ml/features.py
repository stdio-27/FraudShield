"""
Single source of truth for feature engineering.

Both the training pipeline (src/ml/preprocess.py) and the serving layer
(src/api/services.py) import from here so that the two can never drift apart.
"""

import numpy as np
import pandas as pd

V_COLUMNS = [f"V{i}" for i in range(1, 29)]

# Exact column order the scaler and the model were fitted on.
FEATURE_COLUMNS = V_COLUMNS + [
    "Amount",
    "hour_of_day",
    "is_weekend",
    "amount_zscore",
    "amount_log",
    "high_value_flag",
]

HIGH_VALUE_THRESHOLD = 1000.0


def engineer_features(raw: pd.DataFrame, amount_mean: float, amount_std: float) -> pd.DataFrame:
    """
    Build the model feature frame from a raw frame holding ``Time``, ``Amount``
    and ``V1``..``V28``.  ``amount_mean`` / ``amount_std`` are the statistics of
    the *training split*, never of the frame being transformed.
    """
    std = amount_std if amount_std else 1.0

    time_sec = raw["Time"].astype(float)
    amount = raw["Amount"].astype(float)

    out = raw[V_COLUMNS].astype(float).copy()
    out["Amount"] = amount
    out["hour_of_day"] = (time_sec / 3600.0) % 24
    day_of_week = (time_sec // 86400) % 7
    out["is_weekend"] = day_of_week.isin([5, 6]).astype(int)
    out["amount_zscore"] = (amount - amount_mean) / std
    out["amount_log"] = np.log1p(amount)
    out["high_value_flag"] = (amount > HIGH_VALUE_THRESHOLD).astype(int)

    return out[FEATURE_COLUMNS]
