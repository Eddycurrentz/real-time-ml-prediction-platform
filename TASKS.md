# TASKS.md

Legend: [ ] not started, [x] done. Each phase ends with its exit criteria met and a stop for review.
Sizes are rough: S under half a day, M about one day, L multiple days.

## Phase 0: Architecture (this document set)
- [x] ARCHITECTURE.md, DECISIONS.md, TASKS.md
- [x] Approved with defaults locked (see "Locked decisions" at the end)

## Phase 1: Data (M)
- [x] Repo scaffold: `pyproject.toml`, package layout, ruff/pytest config, `.gitignore`, `.env.example`, pre-commit
- [x] Pydantic event schema and validation (`rtml.data.schemas`)
- [x] Synthetic generator CLI (`--rows --anomaly-rate --seed`, drift scenarios, missing values, point-in-time aggregates)
- [x] Document anomaly generation in `docs/data_generation.md`
- [x] Sample dataset in `data/sample/`
- **Exit:** same seed gives byte-identical output; observed anomaly rate within tolerance; unit tests check distributions, schema validity and absence of label leakage; no future-looking aggregates (tested).

**Phase 1 review status:** Verified with deterministic-generation, schema, drift, and prior-only aggregate tests on Python 3.11.

## Phase 2: Kafka (M)
- [x] Compose scaffold: Kafka (KRaft) + Postgres
- [x] SQL migrations for `raw_transactions`, `customer_state`, `dlq_events`
- [x] Producer contract: strips label and emits a clean transaction payload
- [x] Consumer contract: validation, DLQ handling, idempotent upsert, customer_state update
- [ ] Live integration tests against running Kafka/Postgres services and offset resume behaviour
- **Exit:** not yet validated end-to-end against a running local broker and database; unit-level contract checks pass in the current workspace.

## Phase 3: Spark ETL and features (L)
- [x] Shared feature module (`rtml.features`) with point-in-time state logic
- [x] ETL pipeline scaffold: clean parquet read/write and feature generation output
- [x] Feature validation tests for point-in-time logic and feature columns
- [ ] Full PySpark/DQ enforcement and parity test against the online consumer path
- **Exit:** feature logic validated in unit tests; Spark/DQ parity remains a next-step verification task against a running local ETL environment.

## Phase 4: ML (L)
- [x] Baseline training contract: chronological split, sklearn Pipeline, logistic-regression baseline
- [x] Evaluation metrics and threshold selection on validation
- [x] In-memory registry with version aliases for model resolution
- [ ] Compose: MLflow (Postgres backend, volume artifacts)
- [ ] Random Forest and PyTorch MLP training, registry logging, promotion script with gates
- [ ] Reference feature snapshot logged with each model (for drift)
- **Exit:** baseline training and registry logic are implemented and unit-tested; full MLflow and advanced model logging remain open for the next execution step.

## Phase 5: API (M)
- [x] FastAPI app: `/health /ready /predict /predict/batch /model/info`
- [x] Request validation and structured scoring response
- [x] API tests: valid and invalid request handling
- [ ] Model loading by pinned registry version; 503 behaviour when unavailable
- [ ] Request IDs, structured errors, structured logs, Prometheus metrics
- [ ] Consumer wired to the API (retry, DLQ on failure)
- **Exit:** API serving contract is implemented and unit-tested locally; full end-to-end producer -> Kafka -> consumer -> API flow remains a later integration milestone.

## Phase 6: Docker (M)
- [x] Dockerfiles: API and consumer scaffolding
- [x] Complete `docker-compose.yml` (volumes, explicit ports, env vars, health checks)
- [x] Makefile for the local flow
- [x] Docker config validation: `docker compose config --services` accepted the stack definition
- **Exit:** Compose configuration parses successfully. Container startup and end-to-end behavior are unverified; the consumer entry point is currently a stub.

## Phase 7: CI (S-M)
- [x] `ci.yml`: checkout, install, Ruff, unit tests, package build
- [x] Unit-test coverage reporting in CI
- [ ] Integration tests with service containers
- **Exit:** lint, unit tests with coverage, and package build pass locally; service-container CI tests remain open.

## Phase 8: AWS (M)
- [x] Docs: prerequisites, IAM policies as JSON, ECR, EC2, S3, CloudWatch, cost notes
- [x] Scripts run intentionally: `deploy.sh`, `rollback.sh`, `cleanup.sh`
- **Exit:** deployment docs and policy scripts are in the repo and ready for manual use; no AWS resources are created automatically.

## Phase 9: CD (M)
- [x] `deploy.yml`: test, build, tag (git SHA), push to ECR via OIDC, deploy to EC2, health check, rollback on failure, status report
- **Exit:** workflow configuration is present; live AWS deployment, health check, and rollback have not been exercised.

## Phase 10: Monitoring (M)  *(cuttable if time-boxed)*
- [ ] Operational metrics for CPU/memory and consumer lag (HTTP request, latency, error, and prediction counters exist)
- [ ] ML score distribution and PSI/KS drift against a reference snapshot
- [ ] Delayed ground-truth channel and rolling performance metrics
- [x] Prometheus config; docs separating operational from ML monitoring
- **Exit:** partial HTTP/prediction metrics are exposed at `/metrics`; complete operational and ML monitoring remains open.

## Phase 11: A/B testing (M)  *(cuttable if time-boxed)*
- [x] Deterministic customer-hash routing with configurable split
- [ ] Per-arm model scoring, latency, prediction distribution, and ground-truth metrics
- [x] Docs on limitations; statistical test only if sample size supports it, otherwise no significance claims
- **Exit:** deterministic routing is tested; dual-model evaluation and per-arm outcome reporting remain open.

## Phase 12: Final hardening (M)
- [x] Fail-closed API key checks, minimum key length, request-size and batch limits
- [x] Loopback-only Compose ports, required secrets, isolated network, and restricted app containers
- [x] Deployment secret validation, SSH host fingerprint checking, least-privilege CI permissions, and dependency auditing
- [ ] Public-edge TLS/rate limiting, live container verification, and complete external security review
- [x] README (18 required sections), CONTRIBUTING, LICENSE
- [x] `INTERVIEW_GUIDE.md`, `RESUME_BULLETS.md`, `SKILLS_USED.md` strictly from what was implemented
- **Exit:** documentation artifacts exist; full hardening acceptance criteria are not yet evidenced.

---

## Locked decisions (Phase 0 approved with defaults)

These replace the earlier open questions. Changing any of them needs an entry in DECISIONS.md.

| # | Topic | Locked decision |
|---|---|---|
| Q1 | MLflow on AWS | Runs on the same EC2 as the API (compose: api + mlflow + postgres), artifacts in S3. |
| Q2 | Spark | Kept, with the narrow role in D7 (schema enforcement, DQ rules, windowed aggregates, parquet output). Modelling stays in Pandas/scikit-learn. |
| Q3 | PyTorch | Training and MLflow tracking only; not served by default (D12). |
| Q4 | Phases 10-11 | Cuttable if time-boxed. Basic operational metrics ship in Phase 5 regardless. |
| Q5 | Dev machine | Assume 16 GB RAM, Docker Desktop, no GPU (CPU PyTorch). |
| Q6 | Compose approach | Incremental: services are added to `docker-compose.yml` as each phase needs them; Phase 6 completes and verifies it (D13). |

Core scope, architecture, stack and phase order are unchanged.

## Verification snapshot (2026-10-03)

Local checks on Python 3.11.9:
- [x] `py -3.11 -m pytest tests/unit -q --cov=rtml --cov-report=term-missing` (45 passed; 88% total coverage)
- [x] `py -3.11 -m ruff check .`
- [x] `py -3.11 -m ruff format --check .`
- [x] `py -3.11 -m build`
- [x] `pip-audit --progress-spinner off` in a clean project environment (no known vulnerabilities)
- [x] `docker compose config --quiet`
- [ ] Live Compose/integration validation: Docker CLI is installed, but the Docker Desktop engine is not running in this environment.

The checks above validate unit-level behavior, package construction, static quality, and Compose syntax. They do not establish live Kafka/Postgres offset recovery, Spark parity, deployed MLflow/model serving, AWS deployment, or end-to-end CI/CD behavior. Those items remain open until their services and workflows are exercised.
