from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dal.health import HealthRequest, HealthThresholds, PhysicalTable
from dal.documents import dump_document

from tests.application.fixtures import native_document

NOW = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)


class CatalogSnapshot:
    """Offline test implementation of the physical-catalog protocol."""

    def __init__(self, tables: list[PhysicalTable]):
        self.tables = {table.source: table for table in tables}

    def table(self, source: str) -> PhysicalTable | None:
        return self.tables.get(source)


def authored_repository(root: Path, document: dict | None = None) -> tuple[Path, dict]:
    value = deepcopy(document or native_document())
    path = root / "semantic" / "sales.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(dump_document(value), encoding="utf-8")
    return path, value


def request(root: Path, **values) -> HealthRequest:
    return HealthRequest(
        repository_root=root,
        now=NOW,
        thresholds=HealthThresholds(
            source_max_age=timedelta(days=2),
            evidence_max_age=timedelta(days=7),
        ),
        **values,
    )


def table(source: str, columns: dict[str, str], age_days: int = 0) -> PhysicalTable:
    return PhysicalTable(source, columns, NOW - timedelta(days=age_days))
