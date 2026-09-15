"""Small, bounded catalog projections for agent responses."""

from __future__ import annotations

import json
from collections.abc import Mapping

from .models import CatalogObject, Gap, ObjectSummary
from .ranking import publication_status


def summary(item: CatalogObject) -> ObjectSummary:
    return ObjectSummary(item.id, item.kind, item.name, description(item))


def description(item: CatalogObject) -> str | None:
    sources = (item.payload,)
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        for key in ("description", "content"):
            value = source.get(key)
            if isinstance(value, str):
                return _truncate(value, 400)
    return None


def grain(item: CatalogObject) -> object | None:
    return item.payload.get("grain")


def gaps(items: tuple[CatalogObject, ...]) -> tuple[Gap, ...]:
    found = []
    for item in items:
        if item.kind == "join" and not item.payload.get("predicate"):
            found.append(Gap("join_predicate_missing", item.id,
                             "The join has no executable predicate; inspect its evidence before writing SQL."))
        if item.kind != "table":
            continue
        value = grain(item)
        if value is None:
            found.append(Gap("grain_missing", item.id, "Table grain has not been defined."))
    return tuple(found)


def status(item: CatalogObject) -> str | None:
    return publication_status(item)


def _truncate(value: str, length: int) -> str:
    return value if len(value) <= length else value[:length - 1].rstrip() + "…"
