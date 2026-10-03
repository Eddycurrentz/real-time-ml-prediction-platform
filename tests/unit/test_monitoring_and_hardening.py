from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rtml.api.app import app
from rtml.monitoring.routing import route_customer_to_arm

client = TestClient(app)


def test_metrics_endpoint_exposes_prometheus_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    api_key = "monitoring-test-key-with-at-least-32-characters"
    monkeypatch.setenv("RTML_API_KEY", api_key)
    response = client.get(
        "/metrics",
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 200
    assert "rtml_requests_total" in response.text
    assert "rtml_inference_latency_seconds" in response.text


def test_customer_routing_is_stable_and_balanced() -> None:
    assignments = [route_customer_to_arm(f"customer-{idx}") for idx in range(200)]

    assert len(set(assignments)) <= 2
    assert assignments[0] == route_customer_to_arm("customer-0")
    assert assignments.count("treatment") > 0
    assert assignments.count("control") > 0


def test_hardening_documents_exist() -> None:
    docs = [
        Path("README.md"),
        Path("CONTRIBUTING.md"),
        Path("LICENSE"),
        Path("INTERVIEW_GUIDE.md"),
        Path("RESUME_BULLETS.md"),
        Path("SKILLS_USED.md"),
    ]

    for path in docs:
        assert path.exists(), f"Missing {path}"
