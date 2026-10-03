"""Generate reproducible labelled transaction data with point-in-time aggregates."""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID

import numpy as np
import pandas as pd

DriftScenario = Literal["none", "amount_inflation", "category_mix_shift", "new_anomaly_pattern"]
MERCHANT_CATEGORIES = np.array(
    ["grocery", "travel", "electronics", "dining", "utilities", "gambling", "other"]
)
LOCATIONS = np.array(["US-NY", "US-CA", "US-TX", "GB-LON", "CA-ON", "DE-BE"])
DEVICES = np.array(["mobile", "desktop", "pos", "atm"])
BASE_TIME = datetime(2025, 1, 1, tzinfo=UTC)


@dataclass
class CustomerHistory:
    recent: deque[tuple[datetime, float, bool]] = field(default_factory=deque)
    amounts: deque[float] = field(default_factory=deque)
    last_location: str | None = None
    last_device: str | None = None
    last_timestamp: datetime | None = None


def _uuid4(rng: np.random.Generator) -> str:
    return str(UUID(bytes=rng.bytes(16), version=4))


def _next_timestamp(
    previous: datetime | None,
    rng: np.random.Generator,
    archetype: str | None,
) -> datetime:
    if previous is None:
        return BASE_TIME + timedelta(minutes=int(rng.integers(0, 60 * 24)))
    if archetype == "velocity_burst":
        return previous + timedelta(seconds=int(rng.integers(10, 121)))
    if archetype == "odd_hour":
        next_day = previous.date() + timedelta(days=1)
        return datetime(
            next_day.year,
            next_day.month,
            next_day.day,
            int(rng.integers(1, 5)),
            int(rng.integers(0, 60)),
            tzinfo=UTC,
        )
    return previous + timedelta(hours=float(rng.uniform(2, 24)))


def generate_records(
    rows: int = 100_000,
    anomaly_rate: float = 0.02,
    seed: int = 42,
    drift: DriftScenario = "none",
) -> pd.DataFrame:
    """Return labelled rows; every historical aggregate uses earlier events only."""
    if rows <= 0:
        raise ValueError("rows must be greater than zero")
    if not 0 <= anomaly_rate <= 0.5:
        raise ValueError("anomaly_rate must be between 0 and 0.5")
    if seed < 0:
        raise ValueError("seed must be non-negative")
    if drift not in {"none", "amount_inflation", "category_mix_shift", "new_anomaly_pattern"}:
        raise ValueError(f"unsupported drift scenario: {drift}")

    rng = np.random.default_rng(seed)
    customer_count = max(1, min(1_000, rows // 10))
    counts = np.full(customer_count, rows // customer_count, dtype=int)
    counts[: rows % customer_count] += 1
    events: list[dict[str, object]] = []
    archetypes = np.array(
        [
            "amount_spike",
            "velocity_burst",
            "new_context",
            "repeated_fail",
            "card_testing",
            "odd_hour",
        ]
    )

    for customer_number, count in enumerate(counts):
        previous_timestamp: datetime | None = None
        customer_id = f"customer-{customer_number:05d}"
        for event_number in range(int(count)):
            is_intended_anomaly = bool(rng.random() < anomaly_rate)
            archetype = str(rng.choice(archetypes)) if is_intended_anomaly else None
            timestamp = _next_timestamp(previous_timestamp, rng, archetype)
            previous_timestamp = timestamp
            period_progress = event_number / max(1, int(count) - 1)
            is_drift_period = period_progress >= 0.7

            if drift == "category_mix_shift" and is_drift_period:
                category = str(
                    rng.choice(["electronics", "gambling", "travel"], p=[0.45, 0.35, 0.20])
                )
            else:
                category = str(
                    rng.choice(MERCHANT_CATEGORIES, p=[0.28, 0.10, 0.08, 0.22, 0.12, 0.04, 0.16])
                )

            amount = float(rng.lognormal(mean=3.2, sigma=0.85))
            if drift == "amount_inflation" and is_drift_period:
                amount *= 1.8
            if archetype == "amount_spike":
                amount *= float(rng.uniform(2.2, 5.0))
            elif archetype == "card_testing":
                amount = float(rng.uniform(0.50, 3.00))
            elif drift == "new_anomaly_pattern" and is_drift_period and not is_intended_anomaly:
                if category in {"electronics", "gambling"}:
                    amount *= float(rng.uniform(2.0, 3.2))

            event: dict[str, object] = {
                "transaction_id": _uuid4(rng),
                "timestamp": timestamp,
                "customer_id": customer_id,
                "amount": amount,
                "merchant_category": category,
                "transaction_type": str(
                    rng.choice(["purchase", "withdrawal", "transfer", "refund"])
                ),
                "payment_method": str(rng.choice(["card", "bank_transfer", "wallet"])),
                "customer_age": None if rng.random() < 0.08 else int(rng.integers(18, 81)),
                "account_age_days": int(rng.integers(0, 365 * 15 + 1)),
                "location": None if rng.random() < 0.04 else str(rng.choice(LOCATIONS)),
                "device_type": None if rng.random() < 0.06 else str(rng.choice(DEVICES)),
                "_intended_anomaly": is_intended_anomaly,
                "_archetype": archetype,
                "_failure": bool(rng.random() < 0.05),
                "_noise": bool(rng.random() < 0.015),
            }
            events.append(event)

    events.sort(key=lambda row: (row["timestamp"], row["transaction_id"]))
    histories: dict[str, CustomerHistory] = {}
    records: list[dict[str, object]] = []

    for event in events:
        customer_id = str(event["customer_id"])
        history = histories.setdefault(customer_id, CustomerHistory())
        timestamp = event["timestamp"]
        assert isinstance(timestamp, datetime)
        if event["_archetype"] == "new_context":
            event["location"] = str(
                rng.choice(LOCATIONS[LOCATIONS != history.last_location])
                if history.last_location is not None
                else rng.choice(LOCATIONS)
            )
            event["device_type"] = str(
                rng.choice(DEVICES[DEVICES != history.last_device])
                if history.last_device is not None
                else rng.choice(DEVICES)
            )
        window_start = timestamp - timedelta(hours=24)
        while history.recent and history.recent[0][0] < window_start:
            history.recent.popleft()

        recent_failures = sum(failed for _, _, failed in history.recent)
        anomaly = bool(event["_intended_anomaly"])
        if event["_archetype"] == "repeated_fail" and recent_failures < 2:
            anomaly = False
        if drift == "new_anomaly_pattern" and timestamp >= BASE_TIME + timedelta(days=60):
            anomaly = anomaly or (
                event["merchant_category"] in {"electronics", "gambling"}
                and float(event["amount"]) > 100
            )
        anomaly ^= bool(event["_noise"])

        prior_amounts = list(history.amounts)
        record = {key: value for key, value in event.items() if not key.startswith("_")}
        record["transaction_count_24h"] = len(history.recent)
        record["average_transaction_amount"] = (
            sum(prior_amounts) / len(prior_amounts) if prior_amounts else None
        )
        record["previous_failed_transactions"] = recent_failures
        record["is_anomaly"] = anomaly
        records.append(record)

        history.recent.append((timestamp, float(event["amount"]), bool(event["_failure"])))
        history.amounts.append(float(event["amount"]))
        history.last_location = (
            str(event["location"]) if event["location"] is not None else history.last_location
        )
        history.last_device = (
            str(event["device_type"]) if event["device_type"] is not None else history.last_device
        )
        history.last_timestamp = timestamp

    clean_records: list[dict[str, object]] = []
    for record in records:
        clean: dict[str, object] = {}
        for key, value in record.items():
            if key in {
                "customer_age",
                "location",
                "device_type",
                "average_transaction_amount",
            } and pd.isna(value):
                clean[key] = None
            else:
                clean[key] = value
        clean_records.append(clean)

    frame = pd.DataFrame.from_records(clean_records)
    for column in ["customer_age", "location", "device_type", "average_transaction_amount"]:
        if column in frame.columns:
            frame[column] = frame[column].astype(object)
            frame.loc[frame[column].isna(), column] = None
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["transaction_id"] = frame["transaction_id"].astype("string")
    frame["is_anomaly"] = frame["is_anomaly"].astype(bool)
    frame["transaction_count_24h"] = frame["transaction_count_24h"].astype("int64")
    frame["previous_failed_transactions"] = frame["previous_failed_transactions"].astype("int64")
    return frame


def write_dataset(
    output: Path,
    rows: int = 100_000,
    anomaly_rate: float = 0.02,
    seed: int = 42,
    drift: DriftScenario = "none",
) -> pd.DataFrame:
    """Generate and write a deterministic parquet dataset, creating parent folders."""
    frame = generate_records(rows=rows, anomaly_rate=anomaly_rate, seed=seed, drift=drift)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False, compression="zstd")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--anomaly-rate", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--drift",
        choices=["none", "amount_inflation", "category_mix_shift", "new_anomaly_pattern"],
        default="none",
    )
    parser.add_argument("--output", type=Path, default=Path("data/raw/transactions.parquet"))
    args = parser.parse_args()

    frame = write_dataset(args.output, args.rows, args.anomaly_rate, args.seed, args.drift)
    rate = float(frame["is_anomaly"].mean())
    print(f"Wrote {len(frame):,} rows to {args.output} (observed anomaly rate: {rate:.3%})")


if __name__ == "__main__":
    main()
