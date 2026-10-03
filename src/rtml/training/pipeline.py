from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def train_baseline_model(
    features: pd.DataFrame, labels: pd.Series | np.ndarray
) -> dict[str, object]:
    """Train a logistic baseline on a chronological split and return score/threshold metadata."""
    working_features = features.copy()
    working_labels = pd.Series(labels).reset_index(drop=True)
    working_features = working_features.reset_index(drop=True)

    numeric = working_features.select_dtypes(include=[np.number]).copy()
    if numeric.empty:
        raise ValueError("No numeric feature columns are available for training")

    split_idx = max(1, int(len(working_features) * 0.8))
    X_train = numeric.iloc[:split_idx]
    X_valid = numeric.iloc[split_idx:]
    y_train = working_labels.iloc[:split_idx]
    y_valid = working_labels.iloc[split_idx:]

    model = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(class_weight="balanced", max_iter=2000, solver="liblinear"),
            ),
        ]
    )
    model.fit(X_train, y_train)

    probabilities = model.predict_proba(X_valid)[:, 1]
    precision, recall, thresholds = precision_recall_curve(y_valid, probabilities)
    if len(thresholds) == 0:
        threshold = 0.5
        f1_value = float(f1_score(y_valid, (probabilities >= threshold).astype(int)))
    else:
        f1_values = 2.0 * precision[:-1] * recall[:-1] / (precision[:-1] + recall[:-1] + 1e-12)
        best_index = int(np.nanargmax(f1_values)) if len(f1_values) > 0 else 0
        threshold = float(thresholds[best_index])
        f1_value = float(f1_values[best_index])

    predictions = (probabilities >= threshold).astype(int)
    metrics = {
        "pr_auc": float(average_precision_score(y_valid, probabilities)),
        "roc_auc": float(roc_auc_score(y_valid, probabilities)),
        "precision": float(precision_score(y_valid, predictions, zero_division=0)),
        "recall": float(recall_score(y_valid, predictions, zero_division=0)),
        "f1": float(f1_score(y_valid, predictions, zero_division=0)),
        "validation_f1_at_threshold": float(f1_value),
    }

    return {"model": model, "threshold": float(threshold), "metrics": metrics}
