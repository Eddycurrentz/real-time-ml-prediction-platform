from __future__ import annotations

import pandas as pd

from rtml.data.generator import write_dataset
from rtml.etl.pipeline import build_parquet_dataset


def test_etl_reads_raw_parquet_and_writes_ordered_features(tmp_path) -> None:
    source = tmp_path / "raw.parquet"
    target = tmp_path / "features" / "features.parquet"
    raw = write_dataset(source, rows=80, seed=31)

    features = build_parquet_dataset(source, target)
    restored = pd.read_parquet(target)

    assert len(features) == len(raw)
    assert features["amount"].tolist() == raw["amount"].tolist()
    pd.testing.assert_frame_equal(features, restored)
