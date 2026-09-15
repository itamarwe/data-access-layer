"""Stable identity and object-relative edits for native resource files."""

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass

from dal.model import validate_document
from .errors import CanonicalValidationError, CurationError
from .json_patch import apply_patch


@dataclass(frozen=True)
class ObjectLocation:
    index: int
    resource: dict[str, object]

    @property
    def publication_status(self) -> str:
        return str(self.resource.get("status", "published"))


def require_canonical(document: Mapping[str, object]) -> None:
    diagnostics = validate_document(document)
    if diagnostics:
        raise CanonicalValidationError(diagnostics)


def find_object(document: Mapping[str, object], object_id: str) -> ObjectLocation:
    matches = [
        ObjectLocation(index, resource)
        for index, resource in enumerate(document.get("objects", []))
        if isinstance(resource, dict) and resource.get("id") == object_id
    ]
    if len(matches) != 1:
        raise CurationError(f"target object must resolve exactly once: {object_id!r}")
    return matches[0]


def changed_fields(operations: Sequence[object]) -> set[str]:
    fields = set()
    for operation in operations:
        path = operation.get("path") if isinstance(operation, Mapping) else None
        if not isinstance(path, str) or not path.startswith("/") or "/" in path[1:]:
            raise CurationError("patch paths name one resource field; replace arrays or mappings as a whole")
        field = path[1:].replace("~1", "/").replace("~0", "~")
        if field in {"id", "kind"}:
            raise CurationError("a proposal cannot change resource identity or kind")
        fields.add(field)
    return fields


def field_values(resource: Mapping[str, object], fields: set[str]) -> dict[str, object]:
    return {
        key: {"present": key in resource, "value": deepcopy(resource.get(key))}
        for key in sorted(fields)
    }


def apply_scoped_patch(document: Mapping[str, object], object_id: str, operations: Sequence[object]) -> dict[str, object]:
    location = find_object(document, object_id)
    changed_fields(operations)
    proposed = deepcopy(dict(document))
    proposed["objects"][location.index] = apply_patch(location.resource, operations)
    return proposed
