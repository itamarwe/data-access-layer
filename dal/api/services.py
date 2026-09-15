"""Application services available to route handlers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dal.application import BundleCatalog, CatalogService
from dal.curation import CurationService
from dal.health import ActiveBundle, HealthRequest, HealthThresholds, inspect_health

from .config import ServerConfig


@dataclass(frozen=True)
class APIServices:
    catalog: CatalogService
    curation: CurationService
    config: ServerConfig

    @classmethod
    def create(cls, config: ServerConfig) -> "APIServices":
        return cls(
            CatalogService(BundleCatalog(config.bundle)),
            CurationService(config.repository_root),
            config,
        )

    def health(self):
        active = ActiveBundle(self.config.bundle) if (self.config.bundle / "active.json").is_file() else None
        return inspect_health(HealthRequest(
            repository_root=self.config.repository_root,
            now=datetime.now(timezone.utc),
            thresholds=HealthThresholds(timedelta(days=2), timedelta(days=7)),
            active_bundle=active,
            evidence_directory=(self.config.repository_root / "evidence"
                                if (self.config.repository_root / "evidence").is_dir() else None),
        ))

    def compiled_revision(self) -> str | None:
        root = self.config.bundle
        pointer = root / "active.json"
        if pointer.is_file():
            return _revision(pointer)
        manifest = root / "manifest.json"
        return _revision(manifest) if manifest.is_file() else None


def _revision(path: Path) -> str | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("revision")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    return value if isinstance(value, str) else None
