from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from rtml.api.app import app

client = TestClient(app)
TEST_API_KEY = "test-api-key-with-at-least-32-characters"


@pytest.fixture(autouse=True)
def configure_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RTML_API_KEY", TEST_API_KEY)


def test_health_and_ready_endpoints() -> None:
    health = client.get("/health")
    ready = client.get("/ready")

    assert health.status_code == 200
    assert ready.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.json()["status"] == "ready"


def test_dashboard_and_assets_are_served_by_the_api() -> None:
    dashboard = client.get("/")
    script = client.get("/assets/app.js")

    assert dashboard.status_code == 200
    assert 'id="risk-console"' in dashboard.text
    assert script.status_code == 200
    assert '"/predict"' in script.text
    assert dashboard.headers["x-content-type-options"] == "nosniff"


def test_predict_endpoint_scores_valid_request() -> None:
    payload = {
        "transaction_id": "123e4567-e89b-42d3-a456-426614174000",
        "timestamp": "2025-01-03T12:00:00+00:00",
        "customer_id": "customer-1",
        "amount": 18.2,
        "merchant_category": "grocery",
        "transaction_type": "purchase",
        "payment_method": "card",
        "account_age_days": 300,
        "transaction_count_24h": 3,
        "average_transaction_amount": 15.0,
        "location": "US-NY",
        "device_type": "mobile",
        "previous_failed_transactions": 0,
    }

    response = client.post("/predict", json=payload, headers={"X-API-Key": TEST_API_KEY})
    assert response.status_code == 200
    body = response.json()
    assert body["prediction"] in {0, 1}
    assert body["model_version"]
    assert body["transaction_id"] == payload["transaction_id"]


def test_predict_rejects_invalid_payload() -> None:
    payload = {"amount": 0, "customer_id": "c1"}
    response = client.post("/predict", json=payload, headers={"X-API-Key": TEST_API_KEY})
    assert response.status_code == 422


@pytest.mark.parametrize("api_key", [None, "wrong-key"])
def test_predict_rejects_missing_or_invalid_api_key(api_key: str | None) -> None:
    headers = {} if api_key is None else {"X-API-Key": api_key}

    response = client.post("/predict", json={}, headers=headers)

    assert response.status_code == 401


def test_protected_endpoints_fail_closed_without_configured_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RTML_API_KEY")

    response = client.get("/model/info")

    assert response.status_code == 503


def test_protected_endpoints_reject_short_configured_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RTML_API_KEY", "too-short")

    response = client.get("/model/info", headers={"X-API-Key": "too-short"})

    assert response.status_code == 503


def test_readiness_fails_when_api_authentication_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RTML_API_KEY")

    response = client.get("/ready")

    assert response.status_code == 503


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/metrics"), ("GET", "/model/info"), ("POST", "/predict/batch")],
)
def test_sensitive_routes_reject_unauthenticated_requests(method: str, path: str) -> None:
    response = client.request(method, path, json=[] if method == "POST" else None)

    assert response.status_code == 401


def test_prediction_rejects_oversized_request_body() -> None:
    response = client.post(
        "/predict",
        content=" " * (1_048_577),
        headers={"Content-Type": "application/json", "X-API-Key": TEST_API_KEY},
    )

    assert response.status_code == 413


def test_batch_prediction_has_a_hard_item_limit() -> None:
    response = client.post(
        "/predict/batch",
        json=[{}] * 101,
        headers={"X-API-Key": TEST_API_KEY},
    )

    assert response.status_code == 422
