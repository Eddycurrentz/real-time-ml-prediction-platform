from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

REQUESTS_TOTAL = Counter(
    "rtml_requests_total",
    "Total HTTP requests handled by the API.",
    labelnames=("method", "endpoint", "status"),
)

REQUEST_LATENCY = Histogram(
    "rtml_inference_latency_seconds",
    "End-to-end latency in seconds for inference requests.",
    labelnames=("endpoint",),
)

PREDICTIONS_TOTAL = Counter(
    "rtml_predictions_total",
    "Total predictions emitted by the API.",
    labelnames=("arm",),
)

ERRORS_TOTAL = Counter(
    "rtml_errors_total",
    "Total API errors partitioned by HTTP status and endpoint.",
    labelnames=("status", "endpoint"),
)

MODEL_LOADED = Gauge(
    "rtml_model_loaded",
    "1 when a model is loaded and ready to serve.",
)

CONSUMER_LAG = Gauge(
    "rtml_consumer_lag",
    "Approximate number of Kafka messages waiting to be processed by the consumer.",
)

MODEL_LOADED.set(1)
