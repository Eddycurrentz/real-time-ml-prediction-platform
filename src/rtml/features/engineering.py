from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
import pandas as pd

MERCHANT_CATEGORY_ORDER = [
    "grocery",
    "travel",
    "electronics",
    "dining",
    "utilities",
    "gambling",
    "other",
]

FEATURE_COLUMNS = [
    "amount",
    "log_amount",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "amount_vs_customer_average",
    "transaction_count_24h",
    "previous_failed_transactions",
    "failed_transaction_ratio",
    "location_change_indicator",
    "device_change_indicator",
    "transaction_velocity",
    "account_age_days",
    "customer_age",
    "seconds_since_last_transaction",
    "merchant_category_grocery",
    "merchant_category_travel",
    "merchant_category_electronics",
    "merchant_category_dining",
    "merchant_category_utilities",
    "merchant_category_gambling",
    "merchant_category_other",
    "transaction_type_purchase",
    "transaction_type_withdrawal",
    "transaction_type_transfer",
    "transaction_type_refund",
    "payment_method_card",
    "payment_method_bank_transfer",
    "payment_method_wallet",
    "device_type_mobile",
    "device_type_desktop",
    "device_type_pos",
    "device_type_atm",
]


def _is_missing(value: Any) -> bool:
    return value is None or pd.isna(value)


def compute_customer_state_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Append point-in-time historical features using only prior customer events."""
    output = frame.assign(rtml_row_order=np.arange(len(frame))).sort_values(
        ["customer_id", "timestamp"]
    )
    last_location: dict[str, str | None] = {}
    last_device: dict[str, str | None] = {}
    last_timestamp: dict[str, pd.Timestamp] = {}
    prior_amounts: dict[str, list[float]] = {}
    prior_failed_counts: dict[str, int] = {}
    recent_timestamps: dict[str, deque[pd.Timestamp]] = {}

    rows: list[dict[str, Any]] = []
    for row in output.itertuples(index=False):
        customer_id = str(row.customer_id)
        current_ts = pd.Timestamp(row.timestamp)
        prior_amount_list = prior_amounts.setdefault(customer_id, [])
        prior_failed = prior_failed_counts.get(customer_id, 0)
        recent_customer_timestamps = recent_timestamps.setdefault(customer_id, deque())

        current_location = row.location
        current_device = row.device_type
        previous_location = last_location.get(customer_id)
        previous_device = last_device.get(customer_id)
        previous_ts = last_timestamp.get(customer_id)

        seconds_since = np.nan
        if previous_ts is not None:
            delta = (current_ts - previous_ts).total_seconds()
            seconds_since = float(delta) if delta > 0 else 0.0

        average_amount = np.nan
        if prior_amount_list:
            average_amount = float(np.mean(prior_amount_list))

        window_start = current_ts - pd.Timedelta(hours=24)
        while recent_customer_timestamps and recent_customer_timestamps[0] < window_start:
            recent_customer_timestamps.popleft()
        transaction_count_24h = len(recent_customer_timestamps)

        if "transaction_count_24h" in output.columns:
            transaction_count_24h = int(row.transaction_count_24h)

        previous_failed = (
            int(row.previous_failed_transactions)
            if "previous_failed_transactions" in output.columns
            else prior_failed
        )
        failed_ratio = (
            0.0 if transaction_count_24h == 0 else previous_failed / max(1, transaction_count_24h)
        )

        location_change = (
            int(not _is_missing(current_location) and current_location != previous_location)
            if previous_location is not None
            else 0
        )
        device_change = (
            int(not _is_missing(current_device) and current_device != previous_device)
            if previous_device is not None
            else 0
        )
        velocity = 0.0 if np.isnan(seconds_since) else 1.0 / max(seconds_since, 1.0)

        record = {
            "rtml_row_order": int(row.rtml_row_order),
            "customer_id": customer_id,
            "amount": float(row.amount),
            "log_amount": float(np.log(float(row.amount))),
            "hour_of_day": int(current_ts.hour),
            "day_of_week": int(current_ts.dayofweek),
            "is_weekend": int(current_ts.dayofweek >= 5),
            "amount_vs_customer_average": float(row.amount)
            - (float(average_amount) if not np.isnan(average_amount) else float(row.amount)),
            "transaction_count_24h": transaction_count_24h,
            "previous_failed_transactions": previous_failed,
            "failed_transaction_ratio": failed_ratio,
            "location_change_indicator": location_change,
            "device_change_indicator": device_change,
            "transaction_velocity": velocity,
            "account_age_days": int(row.account_age_days),
            "customer_age": int(row.customer_age) if not _is_missing(row.customer_age) else np.nan,
            "seconds_since_last_transaction": seconds_since,
        }

        for category in MERCHANT_CATEGORY_ORDER:
            record[f"merchant_category_{category}"] = int(row.merchant_category == category)

        for value in ["purchase", "withdrawal", "transfer", "refund"]:
            record[f"transaction_type_{value}"] = int(row.transaction_type == value)

        for value in ["card", "bank_transfer", "wallet"]:
            record[f"payment_method_{value}"] = int(row.payment_method == value)

        for value in ["mobile", "desktop", "pos", "atm"]:
            record[f"device_type_{value}"] = int(row.device_type == value)

        rows.append(record)

        last_location[customer_id] = current_location
        last_device[customer_id] = current_device
        last_timestamp[customer_id] = current_ts
        prior_amounts[customer_id].append(float(row.amount))
        prior_failed_counts[customer_id] = previous_failed
        recent_customer_timestamps.append(current_ts)

    return (
        pd.DataFrame(rows)
        .sort_values("rtml_row_order")
        .drop(columns="rtml_row_order")
        .reset_index(drop=True)
    )


def build_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a feature matrix consistent with point-in-time, no-future-data rules."""
    prepared = frame.copy()
    prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], utc=True)
    prepared["customer_id"] = prepared["customer_id"].astype(str)
    features = compute_customer_state_features(prepared)
    return features.reindex(columns=FEATURE_COLUMNS, fill_value=0.0)
