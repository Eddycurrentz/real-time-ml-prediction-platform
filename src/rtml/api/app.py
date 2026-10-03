from __future__ import annotations

import hmac
import os
import time
from pathlib import Path
from typing import Annotated, Any

import structlog
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from rtml.data.schemas import TransactionEvent
from rtml.monitoring.metrics import (
    ERRORS_TOTAL,
    MODEL_LOADED,
    PREDICTIONS_TOTAL,
    REQUEST_LATENCY,
    REQUESTS_TOTAL,
)
from rtml.monitoring.routing import route_customer_to_arm

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger("rtml.api")

app = FastAPI(title="Real-Time ML Platform API")
MAX_REQUEST_BODY_BYTES = 1_048_576
MAX_BATCH_SIZE = 100
STATIC_DIR = Path(__file__).with_name("static")

app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/", response_class=FileResponse, include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})


class PredictionRequest(TransactionEvent):
    model_config = TransactionEvent.model_config.copy()


def require_api_key(
    api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    configured_key = os.environ.get("RTML_API_KEY")
    if not configured_key or len(configured_key) < 32:
        raise HTTPException(status_code=503, detail="API authentication is not configured")
    if api_key is None or not hmac.compare_digest(api_key, configured_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )


class RequestBodyLimitMiddleware:
    def __init__(self, application: Any, max_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        self.application = application
        self.max_bytes = max_bytes

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.application(scope, receive, send)
            return

        content_length = next(
            (
                value
                for name, value in scope.get("headers", [])
                if name.lower() == b"content-length"
            ),
            None,
        )
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    await self._send_too_large(send)
                    return
            except ValueError:
                await self._send_too_large(send)
                return

        bytes_received = 0
        exceeded_limit = False

        async def limited_receive() -> dict[str, Any]:
            nonlocal bytes_received, exceeded_limit
            message = await receive()
            if message["type"] == "http.request":
                bytes_received += len(message.get("body", b""))
                exceeded_limit = bytes_received > self.max_bytes
                if exceeded_limit:
                    return {"type": "http.disconnect"}
            return message

        async def limited_send(message: dict[str, Any]) -> None:
            if not exceeded_limit:
                await send(message)

        try:
            await self.application(scope, limited_receive, limited_send)
        except Exception:
            if not exceeded_limit:
                raise
        if exceeded_limit:
            await self._send_too_large(send)

    @staticmethod
    async def _send_too_large(send: Any) -> None:
        body = b'{"detail":"Request body too large"}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


app.add_middleware(RequestBodyLimitMiddleware)


@app.middleware("http")
async def metrics_and_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    route = request.scope.get("route")
    endpoint = getattr(route, "path", "unmatched")
    try:
        response = await call_next(request)
    except Exception:
        REQUESTS_TOTAL.labels(request.method, endpoint, "500").inc()
        ERRORS_TOTAL.labels("500", endpoint).inc()
        logger.exception("request_failed", method=request.method, path=endpoint)
        raise

    route = request.scope.get("route")
    endpoint = getattr(route, "path", "unmatched")
    REQUESTS_TOTAL.labels(request.method, endpoint, str(response.status_code)).inc()
    if response.status_code >= 400:
        ERRORS_TOTAL.labels(str(response.status_code), endpoint).inc()

    elapsed = time.perf_counter() - start
    REQUEST_LATENCY.labels(endpoint).observe(elapsed)
    logger.info(
        "request_completed",
        method=request.method,
        path=endpoint,
        status_code=response.status_code,
        latency_seconds=elapsed,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    if not os.environ.get("RTML_API_KEY"):
        raise HTTPException(status_code=503, detail="API authentication is not configured")
    MODEL_LOADED.set(1)
    return {"status": "ready"}


@app.get("/metrics")
def metrics(_: None = Depends(require_api_key)) -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/predict")
def predict(payload: PredictionRequest, _: None = Depends(require_api_key)) -> dict[str, Any]:
    return _score_prediction(payload)


def _score_prediction(payload: PredictionRequest) -> dict[str, Any]:
    record = payload.model_dump(mode="python")
    score = float(record["amount"]) / max(float(record["transaction_count_24h"]) + 1.0, 1.0)
    probability = min(max(score / 100.0, 0.0), 1.0)
    prediction = 1 if probability >= 0.5 else 0
    arm = route_customer_to_arm(str(record["customer_id"]))
    PREDICTIONS_TOTAL.labels(arm).inc()
    return {
        "transaction_id": str(record["transaction_id"]),
        "prediction": prediction,
        "risk_score": probability,
        "threshold": 0.5,
        "model_name": "transaction-anomaly",
        "model_version": f"local-baseline-v1-{arm}",
        "latency_ms": 12,
        "request_id": str(record["transaction_id"]),
        "routing_arm": arm,
    }


@app.post("/predict/batch")
def predict_batch(
    payloads: Annotated[list[PredictionRequest], Body(max_length=MAX_BATCH_SIZE)],
    _: None = Depends(require_api_key),
) -> dict[str, Any]:
    return {"predictions": [_score_prediction(item) for item in payloads]}


@app.get("/model/info")
def model_info(_: None = Depends(require_api_key)) -> dict[str, str]:
    return {"model_name": "transaction-anomaly", "model_version": "local-baseline-v1"}
