# Interview Guide

## Project summary

This repository implements a Python baseline for transaction anomaly detection: reproducible synthetic data, point-in-time feature engineering, chronological model evaluation, an in-memory model registry, a FastAPI scoring contract, basic Prometheus metrics, and deterministic customer routing. The Docker Compose file and AWS workflows are scaffolding; service-backed streaming, model-registry serving, and deployment have not been verified. See [TASKS.md](TASKS.md) for current phase status.

## What is implemented

- Deterministic labelled-data generation with missing values and named drift scenarios.
- Shared Pandas feature construction using only prior customer events; output order is preserved for label alignment.
- A scikit-learn logistic-regression baseline with preprocessing fitted on the chronological training partition and metrics/threshold selection on validation data.
- An in-memory registry abstraction for model-version metadata and aliases.
- FastAPI health, readiness, prediction, batch, model-info, and metrics endpoints. The current prediction score is a placeholder formula, not a trained model loaded from the registry.
- An in-memory streaming consumer contract, SQL schema, producer contract, Compose configuration, and unit tests. There is no running Kafka/Postgres adapter or verified offset-resume flow yet.

## Design trade-offs

- Labels stay in the offline training dataset and are excluded from the online event schema.
- Point-in-time features are tested to prevent future-event leakage.
- A chronological train/validation split is used; a held-out test partition and MLflow promotion workflow remain future work.
- The API and consumer boundaries are represented by contracts, but the complete producer-to-database-to-API flow is not implemented.
- Docker and AWS configuration is provided as deployment scaffolding; local containers and AWS deployment were not run in the recorded validation.

## Discussion prompts

- How does the generator ensure aggregates use only prior events?
- Why must feature output order align with the original labels?
- How does fitting preprocessing on training data only avoid validation leakage?
- What would be needed to replace the API's placeholder score with a pinned registry model?
- What delivery and idempotency tests are still needed for a real Kafka/Postgres consumer?
- Which checks are unit-level, and which require Docker or cloud credentials?
