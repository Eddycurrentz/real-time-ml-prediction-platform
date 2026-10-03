from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from typing import Any


class TransactionProducer:
    """Publish event messages to the Kafka transactions topic."""

    def __init__(self, topic: str = "transactions", producer: Any | None = None) -> None:
        self.topic = topic
        self._producer = producer

    def publish(self, event: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(event)
        payload.pop("is_anomaly", None)
        if "transaction_id" not in payload:
            raise ValueError("transaction_id is required")

        if self._producer is not None:
            self._producer.produce(self.topic, json.dumps(payload).encode("utf-8"))
        return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a transaction event to Kafka.")
    parser.add_argument("--topic", default="transactions")
    args = parser.parse_args()
    producer = TransactionProducer(topic=args.topic)
    print(f"Producer ready for topic '{producer.topic}'")


if __name__ == "__main__":
    main()
