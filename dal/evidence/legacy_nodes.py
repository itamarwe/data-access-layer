"""Normalization rules for legacy Legacy node evidence."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from .legacy_common import (
    ClaimSpec, LegacyRecordFactory, column_subject, present, table_subject,
)
from .model import EvidenceLayer as Layer
from .model import EvidenceRecord, SourceKind as Kind

TABLE_CLAIMS = (
    ClaimSpec("schema", "/schema", Layer.PHYSICAL, Kind.DATABASE_SCHEMA),
    ClaimSpec("rows", "/row_count", Layer.PHYSICAL, Kind.DATA_PROFILE, "rows"),
    ClaimSpec("snapshot", "/freshness", Layer.PHYSICAL, Kind.DATA_PROFILE),
    ClaimSpec("partitions", "/partitions", Layer.PHYSICAL, Kind.DATABASE_SCHEMA),
    ClaimSpec("q90", "/usage/query_frequency", Layer.USAGE, Kind.QUERY_LOG, "queries"),
    ClaimSpec("users", "/usage/users", Layer.USAGE, Kind.QUERY_LOG, "users"),
    ClaimSpec("last_used", "/usage/last_used", Layer.USAGE, Kind.QUERY_LOG),
    ClaimSpec("grain", "/grain", Layer.CURATION, Kind.CURATION),
    ClaimSpec("description", "/description", Layer.CURATION, Kind.CURATION),
    ClaimSpec("aliases", "/aliases", Layer.CURATION, Kind.CURATION),
)

COLUMN_CLAIMS = (
    ClaimSpec("data_type", "/datatype", Layer.PHYSICAL, Kind.DATABASE_SCHEMA),
    ClaimSpec("family", "/semantic_type", Layer.PHYSICAL, Kind.DATA_PROFILE),
    ClaimSpec("cardinality_est", "/cardinality", Layer.PHYSICAL, Kind.DATA_PROFILE, "values"),
    ClaimSpec("is_join_key", "/join_key", Layer.PHYSICAL, Kind.DATA_PROFILE),
    ClaimSpec("example_values", "/examples", Layer.PHYSICAL, Kind.DATA_PROFILE),
    ClaimSpec("value_form_inferred", "/format", Layer.PHYSICAL, Kind.DATA_PROFILE),
    ClaimSpec("value_form_basis", "/format", Layer.PHYSICAL, Kind.DATA_PROFILE),
    ClaimSpec("description_schema", "/description", Layer.PHYSICAL, Kind.DATABASE_SCHEMA),
    ClaimSpec("description_model", "/description", Layer.CURATION, Kind.CURATION),
    ClaimSpec("description_curated", "/description", Layer.CURATION, Kind.CURATION),
    ClaimSpec("value_form_curated", "/format", Layer.CURATION, Kind.CURATION),
    ClaimSpec("description_derived", "/description", Layer.CURATION, Kind.CURATION),
    ClaimSpec("description_generated", "/description", Layer.CURATION, Kind.CURATION),
    ClaimSpec("derived_from", "/lineage", Layer.USAGE, Kind.LINEAGE),
)


def table_records(
    row: Mapping[str, object], factory: LegacyRecordFactory,
) -> Iterable[EvidenceRecord]:
    yield from _records("node_tables", table_subject(row["table_name"]), row, TABLE_CLAIMS, factory)


def column_records(
    row: Mapping[str, object], factory: LegacyRecordFactory,
) -> Iterable[EvidenceRecord]:
    subject = column_subject(row["table_name"], row["column"])
    yield from _records("node_columns", subject, row, COLUMN_CLAIMS, factory)


def corrupt_table_records(row, factory):
    subject = table_subject(row["table_name"])
    yield factory.record("corrupt_tables", subject, ClaimSpec(
        "reason", "/corrupt", Layer.PHYSICAL, Kind.DATA_PROFILE,
    ), {"corrupt": True, "reason": str(row.get("reason") or "Source reports table corruption")})


def _records(
    table: str,
    subject: str,
    row: Mapping[str, object],
    specs: tuple[ClaimSpec, ...],
    factory: LegacyRecordFactory,
) -> Iterable[EvidenceRecord]:
    for spec in specs:
        value = row.get(spec.column)
        if present(value):
            yield factory.record(table, subject, spec, value)
