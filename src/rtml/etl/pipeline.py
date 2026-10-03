from __future__ import annotations

from pathlib import Path

import pandas as pd

from rtml.features.engineering import build_feature_frame


def build_parquet_dataset(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    """Read a raw parquet dataset, construct point-in-time features, and write the result."""
    source = Path(input_path)
    target = Path(output_path)
    raw = pd.read_parquet(source)
    features = build_feature_frame(raw)
    target.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(target, index=False, compression="zstd")
    return features


def run_etl(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    return build_parquet_dataset(input_path=input_path, output_path=output_path)
