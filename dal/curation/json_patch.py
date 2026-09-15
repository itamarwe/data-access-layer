"""A small, side-effect-free RFC 6902 subset for authored documents."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from copy import deepcopy

from .errors import CurationError

SUPPORTED_OPERATIONS = frozenset({"add", "remove", "replace"})


def apply_patch(document: Mapping[str, object], operations: Sequence[object]) -> dict[str, object]:
    validate_patch(operations)
    result = deepcopy(dict(document))
    for index, raw_operation in enumerate(operations):
        operation = _validated_operation(raw_operation, index)
        _apply(result, operation, index)
    return result


def validate_patch(operations: object) -> None:
    if not isinstance(operations, list) or not operations:
        raise CurationError("proposal patch must be a non-empty array")
    for index, operation in enumerate(operations):
        _validated_operation(operation, index)


def _validated_operation(raw: object, index: int) -> Mapping[str, object]:
    if not isinstance(raw, Mapping):
        raise CurationError(f"patch operation {index} must be an object")
    operation = raw.get("op")
    path = raw.get("path")
    allowed = {"op", "path", "value"}
    if set(raw) - allowed:
        raise CurationError(f"patch operation {index} has unknown fields")
    if operation not in SUPPORTED_OPERATIONS:
        raise CurationError(f"patch operation {index} has unsupported op {operation!r}")
    if not isinstance(path, str) or not path.startswith("/"):
        raise CurationError(f"patch operation {index} requires an absolute JSON Pointer")
    if operation in {"add", "replace"} and "value" not in raw:
        raise CurationError(f"patch operation {index} requires a value")
    if operation == "remove" and "value" in raw:
        raise CurationError(f"remove operation {index} cannot carry a value")
    return raw


def _apply(document: dict[str, object], operation: Mapping[str, object], index: int) -> None:
    parts = _pointer_parts(str(operation["path"]))
    if not parts:
        raise CurationError(f"patch operation {index} cannot replace the document root")
    parent = _resolve(document, parts[:-1], index)
    token = parts[-1]
    verb = str(operation["op"])
    if isinstance(parent, dict):
        _apply_to_mapping(parent, token, verb, operation, index)
    elif isinstance(parent, list):
        _apply_to_list(parent, token, verb, operation, index)
    else:
        raise CurationError(f"patch operation {index} parent is not a container")


def _apply_to_mapping(
    parent: dict, token: str, verb: str, operation: Mapping[str, object], index: int,
) -> None:
    if verb in {"replace", "remove"} and token not in parent:
        raise CurationError(f"patch operation {index} targets a missing property")
    if verb == "remove":
        del parent[token]
    else:
        parent[token] = deepcopy(operation["value"])


def _apply_to_list(
    parent: list, token: str, verb: str, operation: Mapping[str, object], index: int,
) -> None:
    if verb == "add" and token == "-":
        parent.append(deepcopy(operation["value"]))
        return
    position = _list_index(token, len(parent), verb == "add", index)
    if verb == "add":
        parent.insert(position, deepcopy(operation["value"]))
    elif verb == "replace":
        parent[position] = deepcopy(operation["value"])
    else:
        del parent[position]


def _resolve(document: object, parts: list[str], operation_index: int) -> object:
    value = document
    for token in parts:
        if isinstance(value, dict) and token in value:
            value = value[token]
        elif isinstance(value, list):
            value = value[_list_index(token, len(value), False, operation_index)]
        else:
            raise CurationError(f"patch operation {operation_index} traverses a missing path")
    return value


def _list_index(token: str, length: int, allow_end: bool, operation_index: int) -> int:
    if not token.isdigit() or (len(token) > 1 and token.startswith("0")):
        raise CurationError(f"patch operation {operation_index} has an invalid array index")
    position = int(token)
    limit = length if allow_end else length - 1
    if position > limit:
        raise CurationError(f"patch operation {operation_index} array index is out of bounds")
    return position


def _pointer_parts(pointer: str) -> list[str]:
    if re.search(r"~(?:[^01]|$)", pointer):
        raise CurationError("JSON Pointer contains an invalid escape")
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
