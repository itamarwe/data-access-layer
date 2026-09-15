"""Deterministic serialization for content-addressed evidence snapshots."""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from collections.abc import Iterable, Mapping, Iterator
from datetime import datetime, timezone
from typing import cast

from dal.json_value import FrozenJson, FrozenObject, freeze_json

from .model import (
    ContentReference, EvidenceLayer, EvidenceRecord, EvidenceSource,
    Measurement, SourceKind,
)

SNAPSHOT_FORMAT = "dal.evidence.v1"


def serialize_snapshot(records: Iterable[EvidenceRecord]) -> bytes:
    """Return canonical bytes independent of input iteration order."""
    ordered = sorted(records, key=lambda record: record.record_id)
    stream = io.BytesIO()
    header = f'{{"format":{json.dumps(SNAPSHOT_FORMAT)},"records":['
    stream.write(header.encode("utf-8"))
    seen = set()
    for index, record in enumerate(ordered):
        if record.record_id in seen:
            raise ValueError(f"duplicate evidence record ID: {record.record_id}")
        seen.add(record.record_id)
        if index:
            stream.write(b",")
        document = _record_document(record)
        _record(document)
        encoded = json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
        stream.write(encoded)
    stream.write(b"]}\n")
    return stream.getvalue()


def snapshot_id(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def deserialize_snapshot(payload: bytes) -> tuple[EvidenceRecord, ...]:
    return tuple(_record(value) for value in snapshot_documents(payload.decode("utf-8")))


def snapshot_documents(text: str) -> Iterator[Mapping[str, object]]:
    """Validate the full envelope while decoding only one record tree at a time.

    Consumers must exhaust this iterator before committing work: an invalid
    trailing envelope or duplicate record can be detected after earlier yields.
    """
    decoder = json.JSONDecoder(object_pairs_hook=_unique_object, parse_constant=_reject_constant,
                               parse_float=_finite_float)
    position = 0

    def whitespace():
        nonlocal position
        while position < len(text) and text[position] in " \r\n\t":
            position += 1

    def expect(token):
        nonlocal position
        whitespace()
        if position >= len(text) or text[position] != token:
            raise ValueError(f"expected {token!r} in evidence snapshot at {position}")
        position += 1

    def decode():
        nonlocal position
        whitespace()
        value, position = decoder.raw_decode(text, position)
        return value

    expect("{")
    keys, identifiers = set(), set()
    while True:
        key = decode()
        if not isinstance(key, str) or key not in {"format", "records"} or key in keys:
            raise ValueError("evidence snapshot requires exactly format and records")
        keys.add(key)
        expect(":")
        if key == "format":
            if decode() != SNAPSHOT_FORMAT:
                raise ValueError("unsupported evidence snapshot format")
        else:
            expect("[")
            whitespace()
            if position < len(text) and text[position] != "]":
                while True:
                    value = decode()
                    record = _record(value)
                    if record.record_id in identifiers:
                        raise ValueError(f"duplicate evidence record ID: {record.record_id}")
                    identifiers.add(record.record_id)
                    yield value
                    whitespace()
                    if position < len(text) and text[position] == "]":
                        break
                    expect(",")
            expect("]")
        whitespace()
        if position < len(text) and text[position] == "}":
            expect("}")
            break
        expect(",")
    whitespace()
    if keys != {"format", "records"} or position != len(text):
        raise ValueError("invalid or trailing evidence snapshot content")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON property: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"non-finite JSON number: {value}")


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        _reject_constant(value)
    return result


def _record_document(record: EvidenceRecord) -> dict[str, object]:
    result: dict[str, object] = {
        "claim_path": record.claim_path,
        "claim_value": _json_value(record.claim_value),
        "collected_at": _timestamp(record.collected_at),
        "content": {
            "sha256": record.content.sha256,
            "uri": record.content.uri,
        },
        "layer": record.layer.value,
        "record_id": record.record_id,
        "source": {
            "kind": record.source.kind.value,
            "revision": record.source.revision,
        },
        "subject_id": record.subject_id,
    }
    if record.strength is not None:
        result["strength"] = record.strength
    if record.measurement is not None:
        result["measurement"] = {
            "value": _json_value(record.measurement.value),
            **({"unit": record.measurement.unit} if record.measurement.unit else {}),
        }
    return result


def _record(value: Mapping[str, object]) -> EvidenceRecord:
    required = {"record_id", "layer", "subject_id", "claim_path", "claim_value", "source", "collected_at", "content"}
    if not isinstance(value, Mapping) or not required <= set(value) or set(value) - required - {"strength", "measurement"}:
        raise ValueError("invalid evidence record properties")
    for key in ("record_id", "subject_id", "claim_path", "collected_at"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError(f"evidence {key} must be nonempty text")
    if not value["claim_path"].startswith("/"):
        raise ValueError("evidence claim_path must begin with /")
    source = cast(Mapping[str, str], value["source"])
    content = cast(Mapping[str, str], value["content"])
    measurement = cast(Mapping[str, object] | None, value.get("measurement"))
    for item, keys in ((source, {"kind", "revision"}), (content, {"uri", "sha256"})):
        if not isinstance(item, Mapping) or set(item) != keys or any(not isinstance(v, str) or not v for v in item.values()):
            raise ValueError("invalid evidence source or content reference")
    if re.fullmatch("[0-9a-f]{64}", content["sha256"]) is None:
        raise ValueError("evidence content sha256 must be 64 lowercase hexadecimal characters")
    strength = value.get("strength")
    if strength is not None and (isinstance(strength, bool) or not isinstance(strength, (int, float)) or not math.isfinite(strength) or not 0 <= strength <= 1):
        raise ValueError("evidence strength must be a finite number between 0 and 1")
    if measurement is not None and (not isinstance(measurement, Mapping) or "value" not in measurement or set(measurement) - {"value", "unit"}
                                    or ("unit" in measurement and not isinstance(measurement["unit"], str))):
        raise ValueError("invalid evidence measurement")
    collected_at = datetime.fromisoformat(value["collected_at"].replace("Z", "+00:00"))
    if collected_at.tzinfo is None or collected_at.utcoffset() is None:
        raise ValueError("collected_at must include a timezone")
    return EvidenceRecord(
        record_id=cast(str, value["record_id"]),
        layer=EvidenceLayer(cast(str, value["layer"])),
        subject_id=cast(str, value["subject_id"]),
        claim_path=cast(str, value["claim_path"]),
        claim_value=freeze_json(value["claim_value"]),
        source=EvidenceSource(SourceKind(source["kind"]), source["revision"]),
        collected_at=collected_at,
        content=ContentReference(content["uri"], content["sha256"]),
        strength=cast(float | None, value.get("strength")),
        measurement=(
            Measurement.from_json(
                measurement["value"], cast(str | None, measurement.get("unit")),
            )
            if measurement is not None else None
        ),
    )


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("collected_at must include a timezone")
    utc = value.astimezone(timezone.utc).isoformat(timespec="microseconds")
    return utc.replace("+00:00", "Z")


def _json_value(value: FrozenJson) -> object:
    if isinstance(value, FrozenObject):
        return {key: _json_value(item) for key, item in value.entries}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    return value
