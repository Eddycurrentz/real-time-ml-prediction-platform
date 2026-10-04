# Contributing

Thanks for helping improve the project.

## Workflow

1. Fork or branch from the main branch.
2. Keep changes aligned with the architecture in `ARCHITECTURE.md` and `DECISIONS.md`.
3. Add or update focused tests for behavior changes.
4. Validate locally before opening a PR.

## Local validation

```powershell
python -m pip install -e ".[dev,pipeline,streaming]"
pytest tests/unit -q
ruff check .
```

The base install is the API runtime only; the `pipeline` and `streaming` extras add the offline (`numpy`, `pandas`, `pyarrow`, `scikit-learn`) and Kafka/Postgres (`confluent-kafka`, `psycopg`) dependencies that the test suite needs.

## Coding standards

- keep business logic in `src/rtml`
- prefer point-in-time feature logic and no future leakage
- keep API endpoints stateless and versioned in the registry story
- do not auto-create AWS resources from the repo
