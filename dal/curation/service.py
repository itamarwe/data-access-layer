"""Revision-checked proposals over the same editable, Git-friendly files."""

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

from dal.repository import (
    encode_document, read_document, replace_texts, repository_lock,
    repository_revision, require_revision, semantic_path, semantic_files, load_repository,
)
from .canonical import apply_scoped_patch, changed_fields, field_values, find_object, require_canonical
from .errors import CurationError
from .proposals import ProposalStore, validate_proposal
from .results import CurationResult


class CurationService:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.proposals = ProposalStore(self.root)

    def revision(self) -> str:
        return repository_revision(self.root)

    def list(self, status: str | None = None) -> tuple[dict[str, object], ...]:
        return self.proposals.list(status)

    def get(self, proposal_id: str) -> dict[str, object]:
        return self.proposals.get(proposal_id)

    def create(self, proposal: Mapping[str, object], *, expected_revision: str) -> CurationResult:
        with repository_lock(self.root):
            require_revision(self.root, expected_revision)
            validate_proposal(proposal, required_status="open")
            if proposal["base_revision"] != expected_revision:
                raise CurationError("proposal base_revision must match the repository revision")
            stored = deepcopy(dict(proposal))
            stored.pop("before", None)  # Preconditions are captured here, never trusted from a caller.
            path, current, proposed = self._proposed_document(stored, check_before=False)
            if "object" not in stored:
                resource = find_object(current, str(stored["target"]["object_id"])).resource
                stored["before"] = field_values(resource, changed_fields(stored["patch"]))
            else:
                stored["before"] = {"absent": True}
            proposal_path, content = self.proposals.create_change(stored)
            require_revision(self.root, expected_revision)
            replace_texts({proposal_path: content})
            return self._result(stored)

    def publish(self, proposal_id: str, *, expected_revision: str, decided_by: str | None = None,
                reason: str | None = None) -> CurationResult:
        return self._publish(proposal_id, expected_revision, "publish", decided_by, reason)

    def deprecate(self, proposal_id: str, *, expected_revision: str, decided_by: str | None = None,
                  reason: str | None = None) -> CurationResult:
        return self._publish(proposal_id, expected_revision, "deprecate", decided_by, reason)

    def dismiss(self, proposal_id: str, *, expected_revision: str, decided_by: str | None = None,
                reason: str | None = None) -> CurationResult:
        with repository_lock(self.root):
            require_revision(self.root, expected_revision)
            proposal = self._open_proposal(proposal_id)
            decided = self._decided(proposal, "dismissed", expected_revision, decided_by, reason)
            path, content = self.proposals.update_change(decided)
            require_revision(self.root, expected_revision)
            replace_texts({path: content})
            return self._result(decided)

    def _publish(self, proposal_id, expected_revision, action, decided_by, reason):
        with repository_lock(self.root):
            require_revision(self.root, expected_revision)
            proposal = self._open_proposal(proposal_id)
            path, current, proposed = self._proposed_document(proposal)
            object_id = str(proposal["target"]["object_id"])
            before = "absent" if "object" in proposal else find_object(current, object_id).publication_status
            after = find_object(proposed, object_id).publication_status
            if action == "deprecate" and (before, after) != ("published", "deprecated"):
                raise CurationError("deprecate requires a published to deprecated transition")
            if action == "publish" and after == "deprecated" and before != "deprecated":
                raise CurationError("use deprecate for a resource deprecation")
            # Reviewed source fields must survive later physical refreshes.
            resource = find_object(proposed, object_id).resource
            fields = set(proposal["object"]) if "object" in proposal else changed_fields(proposal["patch"])
            fields -= {"id", "kind", "curation"}
            metadata = resource.setdefault("curation", {})
            metadata["fields"] = sorted(set(metadata.get("fields", [])) | fields)
            decided = self._decided(proposal, "published", expected_revision, decided_by, reason)
            proposal_path, proposal_content = self.proposals.update_change(decided)
            require_revision(self.root, expected_revision)
            replace_texts({path: encode_document(path, proposed), proposal_path: proposal_content})
            return self._result(decided)

    def _proposed_document(self, proposal, *, check_before=True):
        target = proposal["target"]
        object_id = str(target["object_id"])
        repository = load_repository(self.root)
        paths = [
            path for path in semantic_files(self.root)
            if any(item.get("id") == object_id for item in read_document(path)["objects"])
        ]
        if "object" in proposal:
            if paths:
                raise CurationError(f"resource already exists: {object_id}")
            path = semantic_path(self.root, str(target.get("document", "semantic/catalog.yaml")))
            current = read_document(path) if path.exists() else {"version": 1, "objects": []}
            proposed = deepcopy(current)
            proposed["objects"].append(deepcopy(proposal["object"]))
        else:
            if len(paths) != 1:
                raise CurationError(f"target object must resolve exactly once: {object_id!r}")
            path = paths[0]
            # Stable IDs survive file moves and resource array reordering.
            current = read_document(path)
            resource = find_object(current, object_id).resource
            actual = field_values(resource, changed_fields(proposal["patch"]))
            if check_before and actual != proposal.get("before"):
                raise CurationError("proposed fields changed since creation; create a new proposal")
            proposed = apply_scoped_patch(current, object_id, proposal["patch"])
        ids_in_file = {item["id"] for item in current["objects"]}
        combined = {
            "version": 1,
            "objects": [item for item in repository["objects"] if item["id"] not in ids_in_file] + proposed["objects"],
        }
        require_canonical(combined)
        return path, current, proposed

    def _open_proposal(self, proposal_id):
        proposal = self.proposals.get(proposal_id)
        if proposal["status"] != "open":
            raise CurationError(f"proposal is already {proposal['status']}")
        return proposal

    def _decided(self, proposal, status, revision, decided_by, reason):
        decided = deepcopy(dict(proposal))
        decided["status"] = status
        decision = {"repository_revision": revision}
        if decided_by:
            decision["decided_by"] = decided_by
        if reason:
            decision["reason"] = reason
        decided["decision"] = decision
        return decided

    def _result(self, proposal):
        return CurationResult(deepcopy(dict(proposal)), repository_revision(self.root))
