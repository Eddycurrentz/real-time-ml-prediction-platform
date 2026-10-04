# DECISIONS.md

Format: context, target design decision, alternatives considered, consequences. Status: **Accepted as architecture** (Phase 0 approved; defaults locked). Acceptance does not imply the decision has been implemented; delivery status is tracked in [TASKS.md](TASKS.md).

---

## D1. Single installable Python package (`src/rtml`)
**Context:** Features, schemas and config are shared by ETL, training, consumer and API.
**Decision:** One package installed with `pip install -e .`; services are entry points/modules.
**Alternatives:** Separate top-level folders as in the master prompt (needs path hacks or duplicated code); a monorepo of independently published packages (overkill).
**Consequences:** One source of truth for features. The base install is the serving API's runtime set, while the offline numerical stack and the Kafka/Postgres clients are the `pipeline` and `streaming` extras (D21), so each image, workflow and serverless bundle installs only what it runs.

## D2. Stateless API; enrichment in the consumer
**Context:** Some features need per-customer history.
**Decision:** The consumer reads/updates `customer_state` in Postgres and sends enriched requests; the API never touches the database.
**Alternatives:** API reads Postgres directly (couples latency and availability to the DB); a dedicated feature store or Redis (violates Rule 3 at this scale).
**Consequences:** API scales horizontally and survives DB outages. Direct API callers must supply context or accept imputed values (flagged in the response).

## D3. Consumer calls the API over HTTP rather than loading the model
**Decision:** Streaming scoring goes through `POST /predict(/batch)`.
**Alternatives:** Embed the model in the consumer (two serving paths, two places to version and monitor).
**Consequences:** One serving path, one set of metrics, one place for A/B routing. Adds a network hop; mitigated by batch scoring and retries.

## D4. At-least-once delivery with idempotent writes
**Decision:** Manual offset commits after Postgres persistence; upserts keyed by `transaction_id`.
**Alternatives:** Auto-commit (can lose events); Kafka transactions / exactly-once (complex, little benefit here).

## D5. Dead-letter handling: Kafka topic plus Postgres table
**Decision:** Invalid or unscorable events go to `transactions.dlq` and `dlq_events` with reason and source offset.
**Alternatives:** Log-only (the spec prohibits silent loss and logs are hard to replay); DLQ topic only (harder to query).

## D6. Kafka in KRaft mode, `confluent-kafka` client
**Decision:** Single-broker KRaft (no ZooKeeper) in Compose; `confluent-kafka` Python client.
**Alternatives:** ZooKeeper-based images (extra container, legacy); `kafka-python` (less actively maintained, weaker delivery semantics).

## D7. Spark's role is deliberately narrow
**Context:** At roughly 100k rows Spark is not required for performance. The spec says do not use Spark for show.
**Decision:** Spark local mode runs the ETL job: schema enforcement, data-quality rules, cleaning, windowed historical aggregates and partitioned parquet output, runnable on demand (not a long-lived service). Modelling stays in Pandas/scikit-learn.
**Alternatives:** Drop Spark and use Pandas throughout (honest and simpler, but the spec asks for PySpark ETL); Spark Structured Streaming from Kafka (extra moving parts; the consumer already handles streaming).
**Consequences:** README will state plainly that Spark is justified by demonstrating the pattern and scaling path, not by this dataset's size. The ETL contract is parquet in, parquet out, so it could be swapped for Pandas. Open question Q2.

## D8. MLflow aliases instead of stages
**Decision:** `candidate` -> `validated` -> `production` as registry aliases; the API loads `@production`, resolved to a pinned version at startup.
**Alternatives:** Stages (deprecated); tags only (no first-class loading by name).

## D9. Time-based splitting and train-only preprocessing inside a Pipeline
**Decision:** Chronological train/validation/test; imputer, scaler and encoder fitted on train only and logged with the model.
**Alternatives:** Random stratified split (leaks customer behaviour across time); preprocessing outside the model artifact (invites serving skew).

## D10. Primary metric PR-AUC; threshold chosen on validation and stored with the model
**Alternatives:** Accuracy (misleading at 2% positives); ROC-AUC alone (optimistic under heavy imbalance); default 0.5 threshold (arbitrary).

## D11. Class weighting over resampling
**Decision:** `class_weight` / weighted loss. No SMOTE by default.
**Alternatives:** SMOTE/undersampling (can distort probability calibration; can be evaluated later as an experiment).

## D12. Serving model is scikit-learn; PyTorch MLP is registered but not served by default
**Decision:** Keep PyTorch out of the API image initially. It can be served as an A/B treatment later if time permits.
**Alternatives:** Serve both (bigger image, more failure surface). The spec only requires that the PyTorch model is genuinely trained, evaluated and tracked.

## D13. Incremental Compose
**Context:** The master prompt containerises in Phase 6.
**Decision:** Add Postgres/Kafka/MLflow services to `docker-compose.yml` as each phase needs them; Phase 6 finishes the app images and verifies a clean `docker compose up`.
**Alternatives:** Everything in Phase 6 (late integration failures).

## D14. AWS: GitHub OIDC and instance profiles, no static credentials
**Decision:** Actions assumes an IAM role via OIDC for ECR push; the EC2 instance profile grants ECR pull, S3 and CloudWatch.
**Alternatives:** Access keys in GitHub Secrets (long-lived credentials; violates the spirit of Rule 2). Secrets are still used for non-AWS values such as the deployment host.

## D15. Deployment mechanism: SSH/SSM + `docker compose pull && up`
**Decision:** Simple and explainable; includes a health check and rollback to the previous image tag.
**Alternatives:** ECS, Kubernetes, CodeDeploy (excluded by Rule 3).

## D16. Observability stack
**Decision:** `prometheus-client` metrics at `/metrics`, `structlog` JSON logs, CloudWatch Logs on AWS, optional local Prometheus. Drift via PSI and KS tests against a reference snapshot stored with each model version.
**Alternatives:** OpenTelemetry (more than needed now); Evidently (reasonable later; custom PSI/KS keeps behaviour transparent and dependency-light).

## D17. Tooling
**Decision:** `ruff` (lint and format), `pytest` plus `pytest-cov`, `pyproject.toml`, pinned requirement files. Integration tests use Compose-managed services locally and service containers in CI.

---

## D18. MLflow deployed on the same EC2 as the API (resolves Q1)
**Decision:** Compose on EC2 runs api + mlflow + postgres; MLflow artifacts go to S3 via the instance profile.
**Alternatives:** No MLflow in AWS, load pinned model from an S3 URI (cheaper, weaker registry story).
**Consequences:** Needs a t3.small or larger; Postgres on the instance is a single point of failure (documented; RDS is a future improvement).

## D19. Phases 10-11 are cuttable (resolves Q4)
**Decision:** Basic operational metrics ship in Phase 5. Drift detection, delayed ground truth and A/B testing can be dropped or reduced if time-boxed, and docs must then state they are not implemented.

## D20. Development environment assumption (resolves Q5)
**Decision:** 16 GB RAM, Docker Desktop, CPU only. Spark runs on demand with limited memory; PyTorch uses CPU wheels.

## D21. Serverless entrypoint and base-dependency split (Vercel)
**Context:** The API is also deployed as a single FastAPI function on Vercel. Vercel's Python builder has no default entrypoint for this project's `src/` layout, it installs only `[project.dependencies]` (extras are skipped), and it bundles every reachable file into one function with a 500 MB uncompressed limit and no tree-shaking.
**Decision:** Declare `[tool.vercel] entrypoint = "src.rtml.api:app"`, and keep the serving API's runtime set (`fastapi`, `pydantic`, `prometheus-client`, `structlog`, `uvicorn`) as the base dependencies while the offline stack and the Kafka/Postgres clients move to `pipeline` and `streaming` extras.
**Alternatives:** Leave every dependency in `[project.dependencies]` (the unused `numpy`, `pandas`, `pyarrow`, `scikit-learn`, `confluent-kafka` and `psycopg` install measured about 357 MB against the 500 MB limit, and the serving API never imports them); add a root `requirements.txt` (Vercel's manifest loader prefers `pyproject.toml` when both exist, so it would be ignored); serve the API only from a long-lived container (already the AWS path, but it does not give a preview deployment per commit).
**Consequences:** CI and the deploy workflow install `.[dev,pipeline,streaming]`; the streaming image installs `.[streaming]`; the API image and the Vercel function install the base only. The entrypoint was verified by loading `src.rtml.api:app` and exercising `/health`, `/`, `/assets/styles.css`, `/ready`, `/predict` (with and without a key) and `/metrics` against a base-only environment.
