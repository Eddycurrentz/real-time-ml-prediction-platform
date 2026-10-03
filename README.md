# Real-Time Transaction Anomaly Detection

A local-first platform for generating transaction events, training anomaly-detection models, and serving decisions through a stateless API while preserving a clean train/serve boundary.

## 1. Overview

This project simulates a real-time fraud/anomaly monitoring stack:

- synthetic transactions are generated with drift and missing values
- producer/consumer contracts model production-like events; live Kafka and Postgres integration remains unverified
- an in-memory consumer validates events and updates test state; durable service adapters remain future work
- a shared feature module produces point-in-time customer features
- baseline training uses a chronological train/validation split and an in-memory registry
- an API exposes the scoring contract and metrics; the current scorer is a placeholder rather than a loaded trained model

The architecture decisions are recorded in [ARCHITECTURE.md](ARCHITECTURE.md), [DECISIONS.md](DECISIONS.md), and [TASKS.md](TASKS.md).

## 2. Scope and status

The repository contains a tested local baseline and deployment scaffolding. Some service integrations and advanced architecture phases remain incomplete or require external services for verification. Current validation status and phase gaps are tracked in [TASKS.md](TASKS.md). The target design aims for these guardrails; only the behaviors covered by code and tests should be treated as implemented:

- single installable Python package under `src/rtml`
- stateless API contract; full consumer-side enrichment is not wired to the API
- labels remain offline-only for training and monitoring
- shared point-in-time feature logic for offline use; model-backed train/serve parity is not established
- Kafka and Spark are intended to remain local; API/MLflow/Postgres AWS deployment is documented as a target, not validated

## 3. Core capabilities

- deterministic synthetic transaction generation with drift scenarios
- Kafka producer/consumer contracts with DLQ handling
- in-memory customer-state consumer contract and point-in-time feature engineering
- logistic-regression baseline and in-memory registry alias resolution
- FastAPI scoring endpoints and readiness checks
- Prometheus metrics and stable customer routing
- Docker Compose configuration, CI checks, and AWS deployment workflow scaffolding

## 4. Repository layout

```text
.
├── src/rtml/
│   ├── api/
│   ├── data/
│   ├── etl/
│   ├── features/
│   ├── monitoring/
│   ├── streaming/
│   └── training/
├── tests/unit/
├── docs/
├── infrastructure/
├── sql/
├── docker-compose.yml
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
├── LICENSE
├── INTERVIEW_GUIDE.md
├── RESUME_BULLETS.md
├── SKILLS_USED.md
└── TASKS.md
```

## 5. Requirements

- Python 3.11+
- Docker Desktop for local Compose flows
- 16 GB RAM recommended
- CPU-only environment; no GPU required

The project metadata reflects the supported compatibility window. The recorded verification snapshot uses Python 3.11.

## 6. Quickstart

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest tests/unit -q
```

Compose configuration is checked in, but the Docker Desktop engine must be running to build or start containers. The consumer entry point is currently a stub; starting Compose does not verify a complete streaming pipeline.

To build the local stack:

```powershell
Copy-Item .env.example .env
# Edit .env and set unique random URL-safe secrets of at least 32 characters.
docker compose up --build
```

Compose binds the API, PostgreSQL, and Kafka host ports to `127.0.0.1` by default, and requires `RTML_API_KEY` and `POSTGRES_PASSWORD`. Send `X-API-Key` on prediction, batch, metrics, and model-info requests. Do not expose Uvicorn directly to the Internet: use a TLS-terminating reverse proxy with request rate limits and keep the application port private.

When the API is running, open `http://localhost:8000/` for the Risk Desk or `http://localhost:8000/docs` for Swagger. The dashboard calls the live API routes on the same origin, keeps the API key in memory for that browser tab only, and labels the current formula scorer and unconnected Kafka/Postgres/registry paths clearly. The dashboard is not a model-training UI; dataset generation and baseline training remain local Python workflows.

## 7. Data generation

```powershell
rtml-generate --rows 100000 --anomaly-rate 0.02 --seed 42
```

Supported drift scenarios include:

- `amount_inflation`
- `category_mix_shift`
- `new_anomaly_pattern`

See [docs/data_generation.md](docs/data_generation.md) for leakage rules and generation details.

## 8. API usage

The API exposes:

- `GET /health`
- `GET /ready`
- `GET /metrics`
- `POST /predict`
- `POST /predict/batch`
- `GET /model/info`

Example request:

```bash
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $RTML_API_KEY" \
  -d '{
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
    "previous_failed_transactions": 0
  }'
```

## 9. Monitoring and drift signals

The service exposes Prometheus metrics at `/metrics` and records request counts, latency, errors, and prediction totals. This is the operational baseline described in the architecture decisions.

Drift calculations, reference snapshots, and delayed-label evaluation are not implemented. The checked-in metrics currently cover basic API requests, latency, errors, and prediction counts; a Prometheus configuration is provided, but live scraping has not been verified.

## 10. A/B routing

Stable customer-to-arm assignment is implemented in `rtml.monitoring.routing`. Customers are hashed deterministically, so the same customer always routes to the same arm for a given split configuration. The API does not load two distinct models, so this is routing infrastructure rather than a completed A/B experiment.

## 11. Training and registry

The baseline training path uses a chronological train/validation split. The in-memory registry supports aliases:

- `candidate`
- `validated`
- `production`

The API does not yet load a model from the registry; it currently reports a local placeholder model version.

## 12. Deployment

The repository includes local Compose support and AWS deployment scaffolding:

- [docker-compose.yml](docker-compose.yml)
- [docs/aws_deployment.md](docs/aws_deployment.md)
- [infrastructure/scripts/deploy.sh](infrastructure/scripts/deploy.sh)
- [infrastructure/scripts/rollback.sh](infrastructure/scripts/rollback.sh)
- [infrastructure/scripts/cleanup.sh](infrastructure/scripts/cleanup.sh)

## 13. CI and validation

The CI workflow runs Ruff, dependency auditing, unit tests with coverage, and a package build. The deploy workflow repeats those checks before AWS authentication. Neither workflow currently runs service-container integration tests or Docker image builds in the general CI job.

```powershell
pytest tests/unit -q
ruff check .
pip-audit --progress-spinner off
python -m build
```

## 14. Security notes

- no static AWS credentials are committed to the repo
- deployment uses OIDC and EC2 instance roles
- prediction, batch, metrics, and model-info routes require a random API key of at least 32 characters; requests fail closed if the key is missing
- request bodies are capped at 1 MiB and batches at 100 rows
- Compose host ports default to loopback; the Docker service network is internal, and application containers run read-only without Linux capabilities
- CI/deployment run dependency audits; the deployment workflow checks the EC2 SSH host fingerprint and requires strong secrets
- use a TLS-terminating reverse proxy with rate limiting before any external exposure; this repository does not implement TLS or request rate limiting
- deployment environment approval, branch restrictions, and instance security-group rules must be configured by the operator

## 15. Known limitations

This project intentionally stays local-first and intentionally does not claim production-grade scale or all advanced ML monitoring features. It demonstrates the architecture pattern and the necessary implementation mechanics without over-scoping the repository.

## 16. Future roadmap

Potential next steps are:

- MLflow service in Compose and AWS deployment alignment
- delayed ground-truth monitoring channel
- richer model-drift analysis and PSI/KS tests
- A/B arm-specific experiment reporting

## 17. Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution workflow, coding expectations, and local validation commands.

## 18. License

This project is distributed under the MIT License. See [LICENSE](LICENSE) for details.

## 19. Interview and resume material

Supporting narrative and summary artifacts are included in:

- [INTERVIEW_GUIDE.md](INTERVIEW_GUIDE.md)
- [RESUME_BULLETS.md](RESUME_BULLETS.md)
- [SKILLS_USED.md](SKILLS_USED.md)
