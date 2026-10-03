from __future__ import annotations

from datetime import UTC, datetime, timedelta

from rtml.streaming.consumer import StreamingConsumer
from rtml.streaming.producer import TransactionProducer
from rtml.streaming.storage import InMemoryRepository


def _valid_event() -> dict[str, object]:
    return {
        "transaction_id": "123e4567-e89b-42d3-a456-426614174000",
        "timestamp": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        "customer_id": "customer-42",
        "amount": 32.5,
        "merchant_category": "grocery",
        "transaction_type": "purchase",
        "payment_method": "card",
        "account_age_days": 400,
        "transaction_count_24h": 4,
        "average_transaction_amount": 28.0,
        "location": "US-NY",
        "device_type": "mobile",
        "previous_failed_transactions": 1,
    }


def test_transaction_producer_strips_label() -> None:
    producer = TransactionProducer(topic="transactions")
    payload = _valid_event() | {"is_anomaly": True}
    emitted = producer.publish(payload)
    assert emitted["transaction_id"] == payload["transaction_id"]
    assert "is_anomaly" not in emitted
    assert emitted["customer_id"] == "customer-42"


def test_streaming_consumer_accepts_valid_event_and_updates_state() -> None:
    repo = InMemoryRepository()
    consumer = StreamingConsumer(repo=repo)

    result = consumer.process_event(_valid_event(), offset=42)

    assert result["status"] == "accepted"
    assert repo.raw["123e4567-e89b-42d3-a456-426614174000"]["customer_id"] == "customer-42"
    assert repo.customer_state["customer-42"]["last_location"] == "US-NY"
    assert repo.customer_state["customer-42"]["last_device"] == "mobile"
    assert repo.dlq == []


def test_streaming_consumer_moves_malformed_event_to_dlq() -> None:
    repo = InMemoryRepository()
    consumer = StreamingConsumer(repo=repo)

    result = consumer.process_event({"amount": "bad"}, offset=99)

    assert result["status"] == "dlq"
    assert len(repo.dlq) == 1
    assert repo.dlq[0]["offset"] == 99
    assert "validation" in repo.dlq[0]["reason"].lower()


def test_streaming_consumer_is_idempotent_for_duplicate_transactions() -> None:
    repo = InMemoryRepository()
    consumer = StreamingConsumer(repo=repo)

    first = consumer.process_event(_valid_event(), offset=10)
    second = consumer.process_event(_valid_event(), offset=11)

    assert first["status"] == "accepted"
    assert second["status"] == "duplicate"
    assert len(repo.raw) == 1
