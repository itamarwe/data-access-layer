"""Shared construction of deterministic compiled records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping

from .model import CompiledLink, CompiledObject


def compiled_object(
    object_id: str, kind: str, name: str, parent_id: str | None,
    source: str | None, payload: object,
) -> CompiledObject:
    return CompiledObject(
        object_id, kind, name, parent_id, source,
        " ".join(search_strings(payload)), json_payload(payload),
    )


def containment_links(objects: Iterable[CompiledObject]) -> Iterable[CompiledLink]:
    for item in objects:
        if item.parent_id is None:
            continue
        natural_key = f"{item.parent_id}\0{item.object_id}"
        digest = hashlib.sha256(natural_key.encode()).hexdigest()
        yield CompiledLink(
            link_id=f"urn:dal:link:contains:{digest}",
            kind="contains",
            source_id=item.parent_id,
            target_id=item.object_id,
            payload="{}",
        )


def search_strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from search_strings(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from search_strings(item)


def json_payload(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
