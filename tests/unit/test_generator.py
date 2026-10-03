import pandas as pd

from rtml.data.generator import generate_records, write_dataset
from rtml.data.schemas import TransactionEvent


def test_same_seed_produces_identical_records() -> None:
    first = generate_records(rows=500, seed=17)
    second = generate_records(rows=500, seed=17)
    pd.testing.assert_frame_equal(first, second, check_exact=True)


def test_anomaly_rate_and_online_schema_are_reasonable() -> None:
    frame = generate_records(rows=4_000, anomaly_rate=0.05, seed=3)
    assert abs(float(frame["is_anomaly"].mean()) - 0.05) < 0.025
    assert 0.04 < float(frame["customer_age"].isna().mean()) < 0.12
    assert 0.02 < float(frame["location"].isna().mean()) < 0.08
    assert frame["merchant_category"].nunique() >= 6
    assert frame["is_anomaly"].nunique() == 2
    assert "is_anomaly" not in TransactionEvent.model_fields
    for event in frame.drop(columns="is_anomaly").head(100).to_dict(orient="records"):
        TransactionEvent.model_validate(event)


def test_aggregates_use_only_prior_customer_events() -> None:
    frame = generate_records(rows=300, anomaly_rate=0, seed=9)
    for _, group in frame.groupby("customer_id", sort=False):
        prior_amounts: list[float] = []
        prior_window: list[tuple[pd.Timestamp, bool]] = []
        for row in group.itertuples(index=False):
            assert row.transaction_count_24h == sum(
                timestamp >= row.timestamp - pd.Timedelta(hours=24) for timestamp, _ in prior_window
            )
            if prior_amounts:
                assert row.average_transaction_amount == sum(prior_amounts) / len(prior_amounts)
            else:
                assert pd.isna(row.average_transaction_amount)
            prior_amounts.append(row.amount)
            prior_window.append((row.timestamp, False))


def test_drift_scenarios_generate_valid_datasets() -> None:
    for scenario in ("amount_inflation", "category_mix_shift", "new_anomaly_pattern"):
        frame = generate_records(rows=400, seed=12, drift=scenario)
        assert len(frame) == 400
        assert frame["is_anomaly"].dtype == bool


def test_same_arguments_produce_byte_identical_parquet(tmp_path) -> None:
    first_path = tmp_path / "first.parquet"
    second_path = tmp_path / "second.parquet"
    write_dataset(first_path, rows=250, seed=23)
    write_dataset(second_path, rows=250, seed=23)
    assert first_path.read_bytes() == second_path.read_bytes()
