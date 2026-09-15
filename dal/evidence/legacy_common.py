"""Shared conversion primitives for the Legacy DuckDB adapter."""

from __future__ import annotations

from datetime import datetime
from typing import NamedTuple
from urllib.parse import quote

from dal.identity import stable_id

from dal.json_value import freeze_json

from .model import (
    ContentReference, EvidenceLayer, EvidenceRecord, EvidenceSource,
    Measurement, SourceKind, content_digest, stable_record_id,
)


class ClaimSpec(NamedTuple):
    column: str
    claim_path: str
    layer: EvidenceLayer
    source_kind: SourceKind
    unit: str | None = None


class LegacyRecordFactory:
    def __init__(self, source_revision: str, collected_at: datetime):
        self.source_revision = source_revision
        self.collected_at = collected_at

    def record(
        self, table: str, subject_id: str, spec: ClaimSpec, value: object,
    ) -> EvidenceRecord:
        source = EvidenceSource(spec.source_kind, self.source_revision)
        content = ContentReference(
            uri=_content_uri(table, subject_id, spec.column),
            sha256=content_digest(value),
        )
        measurement = (
            Measurement.from_json(value, spec.unit) if spec.unit is not None else None
        )
        return EvidenceRecord(
            record_id=stable_record_id(
                spec.layer, subject_id, spec.claim_path, source, content,
            ),
            layer=spec.layer,
            subject_id=subject_id,
            claim_path=spec.claim_path,
            claim_value=freeze_json(value),
            source=source,
            collected_at=self.collected_at,
            content=content,
            measurement=measurement,
        )


def present(value: object) -> bool:
    return value is not None and value != ""


def table_subject(table_name: object) -> str:
    return stable_id("table", str(table_name))


def column_subject(table_name: object, column: object) -> str:
    return stable_id("column", f"{table_name}.{column}")


def relationship_subject(left: object, right: object) -> str:
    endpoints = sorted((str(left), str(right)))
    return stable_id("join", f"{endpoints[0]}|{endpoints[1]}")


def _content_uri(table: str, subject_id: str, column: str) -> str:
    return f"legacy-duckdb:{table}/{quote(subject_id, safe='')}#/{column}"
