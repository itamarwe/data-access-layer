"""Native graph contract: one resource representation and three evidence layers."""

from collections.abc import Mapping
from dataclasses import dataclass

VERSION = 1
MAPPING_TARGETS = {"entity": {"table", "column"}, "property": {"column"}, "relation": {"join"}}
KINDS = ("database", "table", "column", "join", "entity", "property", "relation", "metric", "doctrine", "gold_query")
COMMON = {"id", "kind", "name", "description", "parent_id", "source", "status", "aliases", "bindings", "object_ids", "evidence_refs", "curation", "recommendation", "restricted", "freshness"}
FIELDS = {
    "database": {"owner"},
    "table": {"grain", "primary_key", "required_filters", "owner"},
    "column": {"data_type", "nullable", "expression", "unit"},
    "join": {"left", "right", "predicate", "cardinality", "join_type", "grain_effect", "required_filters"},
    "entity": {"identifier_ids"},
    "property": {"data_type", "unit"},
    "relation": {"from_id", "to_id", "cardinality"},
    "metric": {"expression", "grain", "required_filters", "unit", "dialect"},
    "doctrine": {"content"},
    "gold_query": {"question", "sql", "dialect", "parameters", "schema_revision"},
}


@dataclass(frozen=True)
class Diagnostic:
    code: str
    pointer: str
    message: str


def validate_document(document: Mapping) -> tuple[Diagnostic, ...]:
    issues = []
    def fail(pointer, message):
        issues.append(Diagnostic("INVALID_CONTEXT", pointer, message))
    if not isinstance(document, Mapping) or document.get("version") != VERSION:
        return (Diagnostic("UNSUPPORTED_VERSION", "/version", "native context version must be 1"),)
    if set(document) - {"version", "objects"}:
        fail("", "document accepts only version and objects")
    objects = document.get("objects")
    if not isinstance(objects, list):
        return (Diagnostic("INVALID_CONTEXT", "/objects", "objects must be an array"),)
    indexed = {}
    for i, item in enumerate(objects):
        pointer = f"/objects/{i}"
        if not isinstance(item, Mapping):
            fail(pointer, "resource must be a mapping")
            continue
        kind = item.get("kind")
        if kind not in KINDS:
            fail(pointer + "/kind", f"unsupported resource kind: {kind!r}")
            continue
        for key in ("id", "name"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                fail(pointer + "/" + key, "must be nonempty text")
        identifier = item.get("id")
        if isinstance(identifier, str):
            if identifier in indexed:
                fail(pointer + "/id", "duplicate stable ID")
            indexed[identifier] = item
        unknown = set(item) - COMMON - FIELDS[kind]
        if unknown:
            fail(pointer, f"unsupported {kind} properties: {', '.join(sorted(unknown))}")
        if item.get("status", "published") not in ("published", "deprecated"):
            fail(pointer + "/status", "canonical status must be published or deprecated")
        for key in ("bindings", "object_ids", "aliases", "required_filters", "identifier_ids", "primary_key"):
            if key in item and (not isinstance(item[key], list) or not all(isinstance(v, str) for v in item[key])):
                fail(pointer + "/" + key, "must be an array of strings")
        if "grain" in item and (not isinstance(item["grain"], Mapping) or "known" in item["grain"]):
            fail(pointer + "/grain", "grain must be a mapping; omit it when unknown")
        if "curation" in item:
            metadata = item["curation"]
            if not isinstance(metadata, Mapping) or not isinstance(metadata.get("fields", []), list) or not all(isinstance(field, str) for field in metadata.get("fields", [])):
                fail(pointer + "/curation", "curation must be a mapping with an optional array of field names")
        for key in ("nullable", "restricted"):
            if key in item and not isinstance(item[key], bool):
                fail(pointer + "/" + key, "must be true or false")
        for key in ("description", "content", "sql", "question", "predicate", "expression", "source", "parent_id", "from_id", "to_id", "data_type", "dialect", "unit"):
            if key in item and not isinstance(item[key], str):
                fail(pointer + "/" + key, "must be text")
        if kind == "column" and not item.get("parent_id"):
            fail(pointer + "/parent_id", "column requires a table")
        if kind == "join":
            left, right = item.get("left"), item.get("right")
            if not all(isinstance(v, list) and v and all(isinstance(x, str) for x in v) for v in (left, right)) or len(left) != len(right):
                fail(pointer, "join requires equally sized nonempty left/right column ID arrays")
        for key in {"doctrine": ("content",), "gold_query": ("question", "sql", "dialect"), "relation": ("from_id", "to_id")}.get(kind, ()):
            if not item.get(key):
                fail(pointer + "/" + key, "required resource property")
    if issues:
        return tuple(issues)
    for i, item in enumerate(objects):
        pointer = f"/objects/{i}"
        refs = [("parent_id", item.get("parent_id")), ("from_id", item.get("from_id")), ("to_id", item.get("to_id"))]
        for key in ("bindings", "object_ids", "identifier_ids", "left", "right"):
            refs.extend((key, value) for value in item.get(key, []))
        for key, identifier in refs:
            if identifier is None:
                continue
            target = indexed.get(identifier)
            if target is None:
                fail(pointer + "/" + key, f"reference does not resolve: {identifier}")
            elif key in {"left", "right"} and target["kind"] != "column":
                fail(pointer + "/" + key, "join endpoints must be columns")
            elif key == "parent_id" and item["kind"] == "column" and target["kind"] != "table":
                fail(pointer + "/parent_id", "column parent must be a table")
            elif key in {"from_id", "to_id"} and item["kind"] == "relation" and target["kind"] not in {"entity", "property"}:
                fail(pointer + "/" + key, "ontology relation endpoints must be entities or properties")
            elif key == "bindings" and target["kind"] not in MAPPING_TARGETS.get(item["kind"], set()):
                fail(pointer + "/bindings", "mappings must go from entity to table/column, property to column, or relation to join")
        if item["kind"] == "join":
            for side in ("left", "right"):
                parents = {indexed[value].get("parent_id") for value in item[side] if value in indexed}
                if len(parents) > 1:
                    fail(pointer + "/" + side, "one side of a join must belong to one table")
        seen, current = {item["id"]}, item
        while current.get("parent_id") in indexed:
            current = indexed[current["parent_id"]]
            if current["id"] in seen:
                fail(pointer + "/parent_id", "containment cycle")
                break
            seen.add(current["id"])
    return tuple(issues)


def require_valid(document: Mapping) -> None:
    diagnostics = validate_document(document)
    if diagnostics:
        raise ValueError("; ".join(f"{d.pointer}: {d.message}" for d in diagnostics))
