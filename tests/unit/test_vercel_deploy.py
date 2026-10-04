"""Guards for the serverless (Vercel) FastAPI deployment configuration.

Vercel installs only the base dependencies and loads the module recorded in
``[tool.vercel]``, so these tests keep the entrypoint loadable and keep the
offline and streaming packages out of the function bundle.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"

API_RUNTIME_DEPENDENCIES = frozenset(
    {"fastapi", "pydantic", "prometheus-client", "structlog", "uvicorn"}
)
PIPELINE_DEPENDENCIES = frozenset({"numpy", "pandas", "pyarrow", "scikit-learn"})
STREAMING_DEPENDENCIES = frozenset({"confluent-kafka", "psycopg"})
HEAVY_MODULES = ("pandas", "numpy", "pyarrow", "sklearn", "scipy", "confluent_kafka", "psycopg")


def read_pyproject() -> dict[str, Any]:
    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))


def dependency_names(requirements: list[str]) -> set[str]:
    """Reduce requirement strings such as ``psycopg[binary]>=3.1,<4`` to ``psycopg``."""
    return {
        requirement.split(">")[0].split("=")[0].split("[")[0].strip()
        for requirement in requirements
    }


def read_entrypoint() -> tuple[str, str]:
    entrypoint = read_pyproject()["tool"]["vercel"]["entrypoint"]
    module_path, _, variable = entrypoint.partition(":")
    assert module_path, "tool.vercel.entrypoint must name a module"
    assert variable, "tool.vercel.entrypoint must name the app variable"
    return module_path, variable


def test_entrypoint_exposes_the_fastapi_app(monkeypatch: Any) -> None:
    module_path, variable = read_entrypoint()
    monkeypatch.syspath_prepend(str(PROJECT_ROOT))

    app = getattr(importlib.import_module(module_path), variable)

    assert type(app).__name__ == "FastAPI"
    assert {route.path for route in app.routes} >= {"/health", "/ready", "/predict", "/metrics"}


def test_heavy_packages_are_extras_not_base_dependencies() -> None:
    project = read_pyproject()["project"]
    base = dependency_names(project["dependencies"])
    extras = project["optional-dependencies"]

    heavy = PIPELINE_DEPENDENCIES | STREAMING_DEPENDENCIES

    assert API_RUNTIME_DEPENDENCIES <= base
    assert not heavy & base, "offline and streaming packages must not be base dependencies"
    assert PIPELINE_DEPENDENCIES <= dependency_names(extras["pipeline"])
    assert STREAMING_DEPENDENCIES <= dependency_names(extras["streaming"])


def test_entrypoint_imports_without_the_offline_or_streaming_packages() -> None:
    module_path, variable = read_entrypoint()
    script = "\n".join(
        (
            "import importlib, json, sys",
            f"sys.path.insert(0, {str(PROJECT_ROOT)!r})",
            f"module = importlib.import_module({module_path!r})",
            f"assert getattr(module, {variable!r}) is not None",
            "print(json.dumps(sorted(sys.modules)))",
        )
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    loaded_modules = set(json.loads(completed.stdout.strip().splitlines()[-1]))

    assert not loaded_modules & set(HEAVY_MODULES), (
        "the API import chain pulled in an extra package"
    )
