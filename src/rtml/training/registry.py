from __future__ import annotations

from collections import defaultdict
from typing import Any


class InMemoryModelRegistry:
    """Minimal registry model for versioned model metadata and alias resolution."""

    def __init__(self) -> None:
        self._versions: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self._aliases: dict[str, dict[str, str]] = defaultdict(dict)

    def register_model(self, model_name: str, version: str, score: float) -> dict[str, Any]:
        entry = {"version": version, "score": float(score), "aliases": set()}
        self._versions[model_name][version] = entry
        return entry

    def set_alias(self, model_name: str, alias: str, version: str) -> None:
        self._aliases[model_name][alias] = version
        if version in self._versions.get(model_name, {}):
            self._versions[model_name][version]["aliases"].add(alias)

    def resolve_alias(self, model_name: str, alias: str) -> str | None:
        version = self._aliases.get(model_name, {}).get(alias)
        return version if version is not None else None

    def resolve_latest(self, model_name: str) -> str | None:
        versions = self._versions.get(model_name, {})
        if not versions:
            return None
        return sorted(versions)[-1]
