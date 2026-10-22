"""Locate the Kaggle credit card fraud CSV regardless of where it was dropped."""

import os
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resolve_dataset_path(explicit_path: Optional[str] = None) -> Optional[str]:
    """
    Search order: explicit argument, ``DATASET_PATH`` env var,
    ``<root>/data/creditcard.csv``, ``<root>/creditcard.csv``.
    """
    candidates = [explicit_path, os.getenv("DATASET_PATH")]
    candidates += [
        os.path.join(PROJECT_ROOT, "data", "creditcard.csv"),
        os.path.join(PROJECT_ROOT, "creditcard.csv"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None
