"""Report unusable join dependencies without deleting authored knowledge."""

from dal.availability import join_dependency_failures, unavailable_from_claims
from dal.evidence import EvidenceLayer, deserialize_snapshot
from dal.model import validate_document
from .model import HealthIssue


def inspect_joins(documents, evidence_directory=None, physical_failures=()):
    objects = [item for document in documents for item in document.value["objects"] if isinstance(item, dict) and "id" in item]
    if validate_document({"version": 1, "objects": objects}):
        return []  # Authored health reports invalid resource shapes and references.
    claims = []
    if evidence_directory is not None:
        for path in sorted(evidence_directory.glob("*.json")):
            try:
                records = deserialize_snapshot(path.read_bytes())
            except (OSError, ValueError):
                continue  # Evidence health owns corrupt snapshot diagnostics.
            claims.extend((item.subject_id, item.collected_at, item.claim_value) for item in records
                          if item.layer == EvidenceLayer.PHYSICAL and item.claim_path == "/exists")
    unavailable = unavailable_from_claims(claims)
    unavailable.update(issue.location for issue in physical_failures if issue.code == "SOURCE_TABLE_MISSING")
    blocked = join_dependency_failures(objects, unavailable)
    published = {item["id"] for item in objects if item.get("status") != "deprecated"}
    return [HealthIssue("JOIN_DEPENDENCY_UNAVAILABLE", identifier,
                        "Join cannot be used: " + "; ".join(reasons),
                        "Restore the endpoint or deprecate/update the join in the canonical files, then run dal validate and dal build. Record confirmed physical absence as physical /exists=false evidence before rebuilding; a health check is read-only.")
            for identifier, reasons in sorted(blocked.items()) if identifier in published]
