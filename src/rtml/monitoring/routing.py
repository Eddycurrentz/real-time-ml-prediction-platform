from __future__ import annotations

import hashlib


def route_customer_to_arm(customer_id: str, control_weight: float = 0.5) -> str:
    """Deterministically assign a customer to the control or treatment arm."""
    if not 0.0 <= control_weight <= 1.0:
        raise ValueError("control_weight must be between 0 and 1 inclusive")

    digest = hashlib.sha256(customer_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / float(0xFFFFFFFF + 1)
    return "treatment" if bucket >= control_weight else "control"
