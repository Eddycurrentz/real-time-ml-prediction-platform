from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class InMemoryRepository:
    """Simple repository implementation used by tests and local development."""

    def __init__(self) -> None:
        self.raw: dict[str, dict[str, Any]] = {}
        self.customer_state: dict[str, dict[str, Any]] = {}
        self.dlq: list[dict[str, Any]] = []

    def save_raw_transaction(self, payload: dict[str, Any]) -> bool:
        transaction_id = str(payload["transaction_id"])
        if transaction_id in self.raw:
            return False
        self.raw[transaction_id] = payload.copy()
        return True

    def upsert_customer_state(
        self,
        customer_id: str,
        *,
        last_location: str | None,
        last_device: str | None,
        last_ts: datetime | None,
    ) -> None:
        state = self.customer_state.setdefault(customer_id, {})
        if last_location is not None:
            state["last_location"] = last_location
        if last_device is not None:
            state["last_device"] = last_device
        if last_ts is not None:
            state["last_ts"] = last_ts.astimezone(UTC)
        state["updated_at"] = datetime.now(UTC)

    def save_dlq_event(
        self,
        *,
        payload: Any,
        reason: str,
        offset: int | None = None,
        transaction_id: str | None = None,
    ) -> dict[str, Any]:
        entry = {
            "transaction_id": transaction_id,
            "payload": payload,
            "reason": reason,
            "offset": offset,
            "received_at": datetime.now(UTC).isoformat(),
        }
        self.dlq.append(entry)
        return entry

    def get_customer_state(self, customer_id: str) -> dict[str, Any]:
        return self.customer_state.get(customer_id, {})
