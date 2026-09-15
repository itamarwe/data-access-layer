"""The three-layer evidence model."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from dal.json_value import FrozenJson, FrozenObject, freeze_json


class EvidenceLayer(str, Enum):
    PHYSICAL = "physical"
    USAGE = "usage"
    CURATION = "curation"


class SourceKind(str, Enum):
    DATABASE_SCHEMA = "database_schema"
    DATA_PROFILE = "data_profile"
    QUERY_LOG = "query_log"
    LINEAGE = "lineage"
    DASHBOARD = "dashboard"
    REPORT = "report"
    ORGANIZATIONAL_COMMUNICATION = "organizational_communication"
    CURATION = "curation"


@dataclass(frozen=True)
class EvidenceSource:
    kind: SourceKind
    revision: str


@dataclass(frozen=True)
class ContentReference:
    uri: str
    sha256: str


@dataclass(frozen=True)
class Measurement:
    value: FrozenJson
    unit: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", freeze_json(self.value))

    @classmethod
    def from_json(cls, value: object, unit: str | None = None) -> "Measurement":
        return cls(freeze_json(value), unit)


@dataclass(frozen=True)
class EvidenceRecord:
    record_id: str
    layer: EvidenceLayer
    subject_id: str
    claim_path: str
    claim_value: FrozenJson
    source: EvidenceSource
    collected_at: datetime
    content: ContentReference
    strength: float | None = None
    measurement: Measurement | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_value", freeze_json(self.claim_value))


def stable_record_id(
    layer: EvidenceLayer,
    subject_id: str,
    claim_path: str,
    source: EvidenceSource,
    content: ContentReference,
) -> str:
    """Identify the same source-backed claim consistently across imports."""
    identity = {
        "claim_path": claim_path,
        "content_sha256": content.sha256,
        "content_uri": content.uri,
        "layer": layer.value,
        "source_kind": source.kind.value,
        "source_revision": source.revision,
        "subject_id": subject_id,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return "urn:dal:evidence:" + hashlib.sha256(encoded).hexdigest()


def content_digest(value: object) -> str:
    frozen = freeze_json(value)
    encoded = _json_transport(frozen)
    payload = json.dumps(encoded, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _json_transport(value: FrozenJson) -> object:
    if isinstance(value, FrozenObject):
        return {key: _json_transport(item) for key, item in value.entries}
    if isinstance(value, tuple):
        return [_json_transport(item) for item in value]
    return value
