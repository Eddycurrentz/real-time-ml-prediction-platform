from __future__ import annotations

import pandas as pd

from rtml.data.generator import generate_records
from rtml.features.engineering import build_feature_frame


def test_feature_frame_has_expected_columns() -> None:
    rows = [
        {
            "transaction_id": "a",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "customer_id": "cust-1",
            "amount": 10.0,
            "merchant_category": "grocery",
            "transaction_type": "purchase",
            "payment_method": "card",
            "customer_age": 30,
            "account_age_days": 200,
            "transaction_count_24h": 0,
            "average_transaction_amount": None,
            "location": "US-NY",
            "device_type": "mobile",
            "previous_failed_transactions": 0,
        },
        {
            "transaction_id": "b",
            "timestamp": "2025-01-01T12:00:00+00:00",
            "customer_id": "cust-1",
            "amount": 20.0,
            "merchant_category": "travel",
            "transaction_type": "withdrawal",
            "payment_method": "wallet",
            "customer_age": 30,
            "account_age_days": 200,
            "transaction_count_24h": 1,
            "average_transaction_amount": 10.0,
            "location": "US-CA",
            "device_type": "desktop",
            "previous_failed_transactions": 0,
        },
    ]
    frame = pd.DataFrame(rows)
    features = build_feature_frame(frame)

    assert features.columns.tolist()[:6] == [
        "amount",
        "log_amount",
        "hour_of_day",
        "day_of_week",
        "is_weekend",
        "amount_vs_customer_average",
    ]
    assert features.iloc[1]["amount_vs_customer_average"] == 10.0
    assert features.iloc[1]["location_change_indicator"] == 1
    assert features.iloc[1]["device_change_indicator"] == 1


def test_feature_frame_preserves_input_row_order() -> None:
    rows = [
        {
            "transaction_id": "a",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "customer_id": "cust-1",
            "amount": 10.0,
            "merchant_category": "grocery",
            "transaction_type": "purchase",
            "payment_method": "card",
            "customer_age": 30,
            "account_age_days": 200,
            "transaction_count_24h": 0,
            "average_transaction_amount": None,
            "location": "US-NY",
            "device_type": "mobile",
            "previous_failed_transactions": 0,
        },
        {
            "transaction_id": "b",
            "timestamp": "2025-01-01T12:00:00+00:00",
            "customer_id": "cust-1",
            "amount": 20.0,
            "merchant_category": "travel",
            "transaction_type": "withdrawal",
            "payment_method": "wallet",
            "customer_age": 30,
            "account_age_days": 200,
            "transaction_count_24h": 1,
            "average_transaction_amount": 10.0,
            "location": "US-CA",
            "device_type": "desktop",
            "previous_failed_transactions": 0,
        },
    ]
    frame = pd.DataFrame(rows[::-1])

    features = build_feature_frame(frame)

    assert features["amount"].tolist() == frame["amount"].tolist()


def test_feature_frame_reconstructs_missing_24_hour_counts() -> None:
    frame = generate_records(rows=80, anomaly_rate=0, seed=31)
    expected_counts = frame["transaction_count_24h"].tolist()

    features = build_feature_frame(frame.drop(columns="transaction_count_24h"))

    assert features["transaction_count_24h"].tolist() == expected_counts


def test_feature_frame_uses_only_prior_customer_history() -> None:
    rows = [
        {
            "transaction_id": "t1",
            "timestamp": "2025-01-01T09:00:00+00:00",
            "customer_id": "c1",
            "amount": 50.0,
            "merchant_category": "electronics",
            "transaction_type": "purchase",
            "payment_method": "card",
            "customer_age": 40,
            "account_age_days": 150,
            "transaction_count_24h": 0,
            "average_transaction_amount": None,
            "location": "US-NY",
            "device_type": "mobile",
            "previous_failed_transactions": 0,
        },
        {
            "transaction_id": "t2",
            "timestamp": "2025-01-01T10:00:00+00:00",
            "customer_id": "c1",
            "amount": 100.0,
            "merchant_category": "electronics",
            "transaction_type": "purchase",
            "payment_method": "card",
            "customer_age": 40,
            "account_age_days": 150,
            "transaction_count_24h": 1,
            "average_transaction_amount": 50.0,
            "location": "US-NY",
            "device_type": "mobile",
            "previous_failed_transactions": 0,
        },
    ]
    frame = pd.DataFrame(rows)
    features = build_feature_frame(frame)

    assert features.iloc[0]["amount_vs_customer_average"] == 0.0
    assert features.iloc[1]["amount_vs_customer_average"] == 50.0
    assert features.iloc[1]["transaction_velocity"] > 0.0
