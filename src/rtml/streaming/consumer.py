from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from rtml.data.schemas import TransactionEvent
from rtml.streaming.storage import InMemoryRepository


class StreamingConsumer:
    """Validate, persist, enrich and score incoming transaction events."""

    def __init__(self, repo: InMemoryRepository | None = None) -> None:
        self.repo = repo or InMemoryRepository()

    def process_message(
        self, message: str | bytes | Mapping[str, Any], *, offset: int | None = None
    ) -> dict[str, Any]:
        if isinstance(message, (str, bytes)):
            try:
                payload = json.loads(message)
            except json.JSONDecodeError as exc:
                return self._dead_letter(
                    payload={"raw": message}, reason=f"json_decode_error: {exc}", offset=offset
                )
        else:
            payload = dict(message)

        return self.process_event(payload, offset=offset)

    def process_event(
        self, payload: Mapping[str, Any], *, offset: int | None = None
    ) -> dict[str, Any]:
        try:
            event = TransactionEvent.model_validate(payload)
        except ValidationError as exc:
            txn_id = payload.get("transaction_id") if isinstance(payload, Mapping) else None
            return self._dead_letter(
                payload=payload,
                reason=f"validation_error: {exc}",
                offset=offset,
                transaction_id=str(txn_id) if txn_id is not None else None,
            )

        txn_id = str(event.transaction_id)
        if txn_id in self.repo.raw:
            return {"status": "duplicate", "transaction_id": txn_id, "offset": offset}

        self.repo.save_raw_transaction(event.model_dump(mode="python"))
        self.repo.upsert_customer_state(
            str(event.customer_id),
            last_location=event.location,
            last_device=event.device_type,
            last_ts=event.timestamp,
        )
        return {"status": "accepted", "transaction_id": txn_id, "offset": offset}

    def _dead_letter(
        self,
        *,
        payload: Any,
        reason: str,
        offset: int | None = None,
        transaction_id: str | None = None,
    ) -> dict[str, Any]:
        self.repo.save_dlq_event(
            payload=payload, reason=reason, offset=offset, transaction_id=transaction_id
        )
        return {
            "status": "dlq",
            "transaction_id": transaction_id,
            "offset": offset,
            "reason": reason,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Process incoming transaction events.")
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    consumer = StreamingConsumer()
    print(f"Consumer ready at offset {args.offset} ({datetime.now(UTC).isoformat()})")
    _ = consumer


if __name__ == "__main__":
    main()
