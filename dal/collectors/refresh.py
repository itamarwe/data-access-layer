"""Offline refresh accepts captured source facts and preserves authored knowledge."""

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from dal.identity import stable_id

from .physical import glue_table
from .types import CollectionResult
from .usage import collect_queries

SOURCE_FIELDS = {"source", "parent_id", "data_type", "nullable"}


def refresh_document(document, incoming_objects):
    result = deepcopy(document)
    by_id = {item["id"]: item for item in result["objects"]}
    for incoming in incoming_objects:
        identifier = incoming["id"]
        if identifier not in by_id:
            item = deepcopy(incoming)
            result["objects"].append(item)
            by_id[identifier] = item
            continue
        current = by_id[identifier]
        if current["kind"] != incoming["kind"]:
            raise ValueError(f"source changed object kind: {identifier}")
        protected = set(current.get("curation", {}).get("fields", []))
        for key in SOURCE_FIELDS - protected:
            if key in incoming:
                current[key] = deepcopy(incoming[key])
        # Authored descriptions, grain, bindings, filters, publication, and join
        # semantics survive refresh. Conflicting source claims remain evidence.
        if not current.get("description") and incoming.get("description"):
            current["description"] = incoming["description"]
    return result


def collect_snapshot(path: Path | str) -> CollectionResult:
    value = json.loads(Path(path).read_text())
    timestamp = datetime.fromisoformat(value["collected_at"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("snapshot collected_at must include a timezone")
    objects, evidence, diagnostics = [], [], []
    databases = set()
    for entry in value.get("tables", []):
        database = entry["database"]
        databases.add(database)
        result = glue_table(database, entry["table"], collected_at=timestamp)
        objects.extend(result.objects)
        evidence.extend(result.evidence)
    objects.extend({"id": stable_id("database", name), "kind": "database", "name": name}
                   for name in sorted(databases))
    usage = collect_queries(value.get("queries", []), collected_at=timestamp)
    known = {item["id"] for item in objects}
    for item in usage.objects:
        if all(endpoint in known for endpoint in item["left"] + item["right"]):
            objects.append(item)
        else:
            diagnostics.append(f"Join {item['id']} has endpoints outside the source snapshot; evidence retained")
    evidence.extend(usage.evidence)
    diagnostics.extend(usage.diagnostics)
    return CollectionResult(tuple(objects), tuple(evidence), tuple(diagnostics))
