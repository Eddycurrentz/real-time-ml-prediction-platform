from __future__ import annotations

import pandas as pd

from rtml.data.generator import generate_records
from rtml.features.engineering import build_feature_frame
from rtml.training.pipeline import train_baseline_model
from rtml.training.registry import InMemoryModelRegistry


def test_train_baseline_model_builds_features_and_metrics() -> None:
    frame = generate_records(rows=600, anomaly_rate=0.06, seed=11)
    features = build_feature_frame(frame)
    labels = frame["is_anomaly"].astype(int)

    result = train_baseline_model(features, labels)

    assert result["threshold"] > 0.0
    assert result["threshold"] < 1.0
    assert result["metrics"]["pr_auc"] >= 0.0
    assert result["metrics"]["f1"] >= 0.0
    assert result["model"] is not None


def test_training_imputer_is_fit_only_on_chronological_training_rows() -> None:
    features = pd.DataFrame({"amount": [None, *range(2, 17), 100.0, 200.0, 300.0, 400.0]})
    labels = pd.Series([0, 1] * 10)

    result = train_baseline_model(features, labels)

    model = result["model"]
    assert model.named_steps["imputer"].statistics_[0] == 9.0


def test_registry_tracks_aliases_and_resolves_latest_version() -> None:
    registry = InMemoryModelRegistry()
    registry.register_model("transaction-anomaly", "v1", 0.74)
    registry.register_model("transaction-anomaly", "v2", 0.82)
    registry.set_alias("transaction-anomaly", "candidate", "v2")

    assert registry.resolve_alias("transaction-anomaly", "candidate") == "v2"
    assert registry.resolve_alias("transaction-anomaly", "production") is None
