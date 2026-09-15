from pathlib import Path
from urllib.parse import quote

from dal.documents import dump_document
from dal.repository import repository_revision
from tests.application.fixtures import native_document

DOCUMENT = "semantic/sales.yaml"
TABLE_ID = "urn:dal:table:orders"


def repository(root: Path, *, published_table: bool = False) -> Path:
    document = native_document()
    document["objects"][0]["status"] = "published"
    path = root / DOCUMENT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_document(document), encoding="utf-8")
    return path


def proposal(root: Path, *, patch=None, proposal_id="urn:dal:proposal:describe-orders"):
    return {
        "id": proposal_id, "status": "open",
        "target": {"document": DOCUMENT, "object_id": TABLE_ID},
        "base_revision": repository_revision(root),
        "patch": patch or [{"op": "add", "path": "/description", "value": "Published order facts."}],
        "reason": "Document the table for agents.",
        "created_by": {"kind": "curator", "id": "user:one"},
    }


def proposal_path(root: Path, proposal_id: str) -> Path:
    return root / "proposals" / (quote(proposal_id, safe="") + ".proposal.yaml")
