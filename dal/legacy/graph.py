"""One-way import of the former DAL nodes/edges/join-specs JSON export."""

import json
from datetime import datetime, timezone
from pathlib import Path

from dal.evidence import SourceKind, content_digest
from dal.collectors.types import claim
from dal.identity import stable_id

from .models import CatalogImport, ImportDiagnostic
from .values import publication


class LegacyGraphImporter:
    """Accept a graph directory or a JSON object with nodes and join_specs arrays."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def convert(self, model_name: str = "imported"):
        if self.path.is_dir():
            raw = {key: json.loads((self.path / filename).read_text())
                   if (self.path / filename).is_file() else []
                   for key, filename in (("nodes", "nodes.json"), ("edges", "edges.json"), ("join_specs", "join_specs.json"))}
        else:
            raw = json.loads(self.path.read_text())
        if not isinstance(raw, dict) or not isinstance(raw.get("nodes"), list):
            raise ValueError("old graph requires a nodes array")
        revision = content_digest(raw)
        # Exported files do not promise a measurement timestamp. The file time
        # records capture provenance; imported measurements retain source fields.
        timestamp = datetime.fromtimestamp(self.path.stat().st_mtime, timezone.utc)
        objects, evidence, diagnostics, identities = [], [], [], {}
        for node in raw["nodes"]:
            kind = node.get("kind")
            if kind not in {"database", "table", "column"}:
                diagnostics.append(ImportDiagnostic("UNSUPPORTED_NODE", str(node.get("id")), f"Node kind {kind} has no import mapping"))
                continue
            identifier = stable_id(kind, node["id"])
            identities[node["id"]] = identifier
            item = {"id": identifier, "kind": kind, "name": node.get("name") or node["id"],
                    "source": node["id"], "status": publication(node.get("status"))}
            if kind == "column":
                item["parent_id"] = stable_id("table", node.get("table_id") or node["id"].rsplit(".", 1)[0])
                if node.get("type"):
                    item["data_type"] = node["type"]
            if kind == "table" and node.get("database"):
                item["parent_id"] = stable_id("database", node["database"])
            description = node.get("description") or node.get("comment")
            if isinstance(description, str) and description:
                item["description"] = description
            if node.get("grain"):
                item["grain"] = node["grain"] if isinstance(node["grain"], dict) else {"description": str(node["grain"])}
            objects.append(item)
            for key, source_kind in (
                ("usage", SourceKind.QUERY_LOG), ("profile", SourceKind.DATA_PROFILE),
                ("freshness", SourceKind.DATA_PROFILE), ("row_count_estimate", SourceKind.DATA_PROFILE),
                ("partition_keys", SourceKind.DATABASE_SCHEMA), ("comment", SourceKind.DATABASE_SCHEMA),
            ):
                if node.get(key) is not None:
                    evidence.append(claim(identifier, f"/{key}", node[key], kind=source_kind,
                                          revision=revision, collected_at=timestamp, uri=f"legacy-json:{node['id']}#{key}"))
        joins = 0
        for spec in raw.get("join_specs", []):
            left, right = spec.get("left"), spec.get("right")
            if left not in identities or right not in identities:
                diagnostics.append(ImportDiagnostic("MISSING_JOIN_ENDPOINT", str(spec.get("id")), "Join omitted because an endpoint is absent"))
                continue
            identifier = stable_id("join", "|".join(sorted((left, right))))
            item = {"id": identifier, "kind": "join", "name": f"{left} ↔ {right}",
                    "left": [identities[left]], "right": [identities[right]]}
            # Candidate-generated SQL is not accepted knowledge. Only preserve
            # a condition whose source is usage or explicitly curated metadata.
            support = spec.get("evidence") or {}
            usage = support.get("usage_evidence") or {}
            observed = isinstance(usage, dict) and (usage.get("explicit_joins") or 0) > 0
            if spec.get("condition") and (observed or spec.get("status") in {"approved", "curated", "published"}):
                item["predicate"] = spec["condition"]
                if spec.get("additional_conditions"):
                    item["required_filters"] = spec["additional_conditions"]
                if spec.get("cardinality"):
                    item["cardinality"] = spec["cardinality"]
            objects.append(item)
            for key, kind in (("physical_evidence", SourceKind.DATA_PROFILE), ("usage_evidence", SourceKind.QUERY_LOG)):
                if support.get(key):
                    evidence.append(claim(identifier, "/physical" if key == "physical_evidence" else "/usage",
                                          support[key], kind=kind, revision=revision, collected_at=timestamp,
                                          uri=f"legacy-json:join/{spec.get('id', '')}#{key}"))
            joins += 1
        for edge in raw.get("edges", []):
            if edge.get("kind") in {"HAS_COLUMN", "JOINS_WITH"}:
                continue
            subject = identities.get(edge.get("src"))
            if subject:
                evidence.append(claim(subject, "/lineage" if edge.get("kind") == "DERIVED_FROM" else "/usage/relationship",
                                      edge, kind=SourceKind.LINEAGE if edge.get("kind") == "DERIVED_FROM" else SourceKind.QUERY_LOG,
                                      revision=revision, collected_at=timestamp, uri=f"legacy-json:edge/{edge.get('id', '')}"))
        return CatalogImport({"version": 1, "objects": objects}, sum(x["kind"] == "table" for x in objects),
                             sum(x["kind"] == "column" for x in objects), joins, tuple(diagnostics), tuple(evidence))
