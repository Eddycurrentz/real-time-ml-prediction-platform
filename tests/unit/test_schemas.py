from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from rtml.data.schemas import TrainingRecord, TransactionEvent


def valid_event() -> dict[str, object]:
    return {
        "transaction_id": str(uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "customer_id": "customer-1",
        "amount": 12.5,
        "merchant_category": "grocery",
        "transaction_type": "purchase",
        "payment_method": "card",
        "account_age_days": 365,
        "transaction_count_24h": 0,
        "previous_failed_transactions": 0,
    }


def test_event_accepts_valid_payload_and_optional_missing_fields() -> None:
    event = TransactionEvent.model_validate(valid_event())
    assert event.customer_age is None
    assert event.timestamp.tzinfo == UTC


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": 0},
        {"customer_age": 17},
        {"merchant_category": "unknown"},
        {"timestamp": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
        {"is_anomaly": True},
    ],
)
def test_event_rejects_invalid_or_labelled_payload(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        TransactionEvent.model_validate(valid_event() | changes)


def test_training_record_accepts_label_without_changing_event_contract() -> None:
    record = TrainingRecord.model_validate(valid_event() | {"is_anomaly": False})
    assert record.is_anomaly is False
