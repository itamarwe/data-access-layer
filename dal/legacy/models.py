"""Results of one-way imports into native DAL documents."""

from dataclasses import dataclass

from dal.evidence import EvidenceRecord


@dataclass(frozen=True)
class ImportDiagnostic:
    code: str
    subject: str
    message: str


@dataclass(frozen=True)
class CatalogImport:
    document: dict[str, object]
    tables: int
    fields: int
    relationships: int
    diagnostics: tuple[ImportDiagnostic, ...]
    evidence: tuple[EvidenceRecord, ...] = ()
    omitted_records: tuple[dict, ...] = ()
