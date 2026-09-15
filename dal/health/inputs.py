"""Explicit offline inputs for deterministic health checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Mapping, Protocol


@dataclass(frozen=True)
class PhysicalTable:
    source: str
    columns: Mapping[str, str]
    data_updated_at: datetime | None


class PhysicalCatalogSnapshot(Protocol):
    """A collected catalog view; implementations must not perform live I/O here."""

    def table(self, source: str) -> PhysicalTable | None:
        """Return the table captured for an exact physical source name."""
        ...


@dataclass(frozen=True)
class HealthThresholds:
    source_max_age: timedelta
    evidence_max_age: timedelta

    def __post_init__(self) -> None:
        if self.source_max_age < timedelta(0) or self.evidence_max_age < timedelta(0):
            raise ValueError("health thresholds cannot be negative")


@dataclass(frozen=True)
class ActiveBundle:
    root: Path
    expected_revision: str | None = None


@dataclass(frozen=True)
class HealthRequest:
    repository_root: Path
    now: datetime
    thresholds: HealthThresholds
    physical_catalog: PhysicalCatalogSnapshot | None = None
    active_bundle: ActiveBundle | None = None
    evidence_directory: Path | None = None

    def __post_init__(self) -> None:
        if self.now.tzinfo is None or self.now.utcoffset() is None:
            raise ValueError("health check time must include a timezone")
