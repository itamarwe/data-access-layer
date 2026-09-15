"""Strict proposal records stored as deterministic YAML."""

from __future__ import annotations

import re
from urllib.parse import quote
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

from dal.repository import RecordAlreadyExists, RecordNotFound, encode_document, read_document

from .errors import CurationError
from .json_patch import validate_patch

PROPOSAL_ID = re.compile(r"^urn:dal:proposal:[A-Za-z0-9][A-Za-z0-9._:-]*$")
PROPOSAL_STATES = frozenset({"open", "published", "dismissed"})


class ProposalStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.directory = self.root / "proposals"

    def get(self, proposal_id: str) -> dict[str, object]:
        path = self._path(proposal_id)
        if not path.is_file():
            raise RecordNotFound(f"proposal not found: {proposal_id}")
        wrapper = read_document(path)
        proposal = wrapper.get("proposal")
        validate_proposal(proposal)
        return deepcopy(proposal)  # type: ignore[arg-type]

    def list(self, status: str | None = None) -> tuple[dict[str, object], ...]:
        if status is not None and status not in PROPOSAL_STATES:
            raise CurationError(f"unsupported proposal status: {status!r}")
        if not self.directory.is_dir():
            return ()
        proposals = [self._read_path(path) for path in sorted(self.directory.glob("*.proposal.yaml"))]
        return tuple(
            proposal for proposal in proposals
            if status is None or proposal["status"] == status
        )

    def create_change(self, proposal: Mapping[str, object]) -> tuple[Path, str]:
        validate_proposal(proposal, required_status="open")
        path = self._path(str(proposal["id"]))
        if path.exists():
            raise RecordAlreadyExists(f"proposal already exists: {proposal['id']}")
        return path, encode_document(path, {"proposal": deepcopy(dict(proposal))})

    def update_change(self, proposal: Mapping[str, object]) -> tuple[Path, str]:
        validate_proposal(proposal)
        path = self._path(str(proposal["id"]))
        if not path.is_file():
            raise RecordNotFound(f"proposal not found: {proposal['id']}")
        return path, encode_document(path, {"proposal": deepcopy(dict(proposal))})

    def _read_path(self, path: Path) -> dict[str, object]:
        proposal = read_document(path).get("proposal")
        validate_proposal(proposal)
        return deepcopy(proposal)  # type: ignore[arg-type]

    def _path(self, proposal_id: str) -> Path:
        if not PROPOSAL_ID.fullmatch(proposal_id):
            raise CurationError(f"invalid proposal id: {proposal_id!r}")
        name = quote(proposal_id, safe="") + ".proposal.yaml"
        return self.directory / name


def validate_proposal(value: object, required_status: str | None = None) -> None:
    if not isinstance(value, Mapping):
        raise CurationError("proposal must be an object")
    allowed = {
        "id", "status", "target", "base_revision", "patch", "reason",
        "created_by", "decision", "before", "object",
    }
    required = {"id", "status", "target", "base_revision"}
    if required - set(value) or set(value) - allowed:
        raise CurationError("proposal fields do not match the closed contract")
    if not isinstance(value["id"], str) or not PROPOSAL_ID.fullmatch(value["id"]):
        raise CurationError("proposal id must be a stable DAL proposal URN")
    status = value["status"]
    if not isinstance(status, str) or status not in PROPOSAL_STATES or (required_status and status != required_status):
        raise CurationError(f"proposal must have status {required_status or 'open|published|dismissed'}")
    _validate_target(value["target"])
    if not isinstance(value["base_revision"], str) or not value["base_revision"].startswith("sha256:"):
        raise CurationError("proposal base_revision must be a repository revision")
    if ("patch" in value) == ("object" in value):
        raise CurationError("provide exactly one of patch or object")
    if "patch" in value:
        validate_patch(value["patch"])
    else:
        resource = value["object"]
        if not isinstance(resource, Mapping) or resource.get("id") != value["target"]["object_id"]:
            raise CurationError("new object id must match target object_id")
    if "before" in value and not isinstance(value["before"], Mapping):
        raise CurationError("proposal preconditions must be an object")
    _validate_optional_text(value, "reason")
    if "created_by" in value:
        _validate_curator(value["created_by"])
    if status == "open" and "decision" in value:
        raise CurationError("an open proposal cannot have a decision")
    if status != "open" and not isinstance(value.get("decision"), Mapping):
        raise CurationError("a decided proposal must record its decision")
    if status != "open":
        _validate_decision(value["decision"])


def _validate_target(value: object) -> None:
    if not isinstance(value, Mapping) or "object_id" not in value or set(value) - {"document", "object_id"}:
        raise CurationError("proposal target requires object_id and optional document")
    if not all(isinstance(value[key], str) and value[key] for key in value):
        raise CurationError("proposal target values must be non-empty strings")


def _validate_curator(value: object) -> None:
    if not isinstance(value, Mapping) or set(value) != {"kind", "id"}:
        raise CurationError("created_by requires only kind and id")
    if value["kind"] != "curator" or not isinstance(value["id"], str) or not value["id"]:
        raise CurationError("created_by must identify one curator")


def _validate_decision(value: object) -> None:
    assert isinstance(value, Mapping)
    allowed = {"repository_revision", "decided_by", "reason"}
    if set(value) - allowed or "repository_revision" not in value:
        raise CurationError("decision fields do not match the closed contract")
    revision = value["repository_revision"]
    if not isinstance(revision, str) or not revision.startswith("sha256:"):
        raise CurationError("decision repository_revision is invalid")
    _validate_optional_text(value, "decided_by")
    _validate_optional_text(value, "reason")


def _validate_optional_text(value: Mapping[str, object], field: str) -> None:
    if field in value and (not isinstance(value[field], str) or not value[field]):
        raise CurationError(f"{field} must be a non-empty string")
