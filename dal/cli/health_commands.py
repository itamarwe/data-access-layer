"""Offline health command over explicit local snapshots."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dal.health import (
    ActiveBundle, HealthRequest, HealthThresholds, PhysicalTable, inspect_health,
)

from .contracts import CommandOutcome
from .files import read_document


class LocalPhysicalCatalog:
    def __init__(self, path: str):
        document = read_document(path)
        self.tables = {
            str(item["source"]): PhysicalTable(
                source=str(item["source"]),
                columns=dict(item["columns"]),
                data_updated_at=_timestamp(str(item["data_updated_at"])) if item.get("data_updated_at") else None,
            )
            for item in document.get("tables", [])
        }

    def table(self, source: str) -> PhysicalTable | None:
        return self.tables.get(source)


def register(commands) -> None:
    health = commands.add_parser("health", help="Inspect local DAL repository health.")
    health.add_argument("--repository", default=argparse.SUPPRESS)
    health.add_argument("--now", default=None, help="Timezone-aware ISO-8601 timestamp; defaults to now.")
    health.add_argument("--source-max-age-hours", type=float, default=24.0)
    health.add_argument("--evidence-max-age-hours", type=float, default=168.0)
    health.add_argument("--physical-catalog")
    health.add_argument("--active-bundle")
    health.add_argument("--expected-bundle-revision")
    health.add_argument("--evidence-directory")
    health.set_defaults(handler=run)


def run(arguments: argparse.Namespace) -> CommandOutcome:
    root = Path(arguments.repository)
    physical = (
        LocalPhysicalCatalog(arguments.physical_catalog)
        if arguments.physical_catalog else None
    )
    bundle = (
        ActiveBundle(
            Path(arguments.active_bundle), arguments.expected_bundle_revision,
        )
        if arguments.active_bundle else
        ActiveBundle(root / ".dal" / "query") if (root / ".dal" / "query" / "active.json").is_file() else None
    )
    request = HealthRequest(
        repository_root=Path(arguments.repository),
        now=_timestamp(arguments.now) if arguments.now else datetime.now(timezone.utc),
        thresholds=HealthThresholds(
            timedelta(hours=arguments.source_max_age_hours),
            timedelta(hours=arguments.evidence_max_age_hours),
        ),
        physical_catalog=physical,
        active_bundle=bundle,
        evidence_directory=(
            Path(arguments.evidence_directory)
            if arguments.evidence_directory else root / "evidence" if (root / "evidence").is_dir() else None
        ),
    )
    result = inspect_health(request)
    return CommandOutcome(result, 0 if result.healthy else 1)


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
