"""Stable records emitted by the native compiler."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompiledObject:
    object_id: str
    kind: str
    name: str
    parent_id: str | None
    source: str | None
    search_text: str
    payload: str


@dataclass(frozen=True)
class CompiledLink:
    link_id: str
    kind: str
    source_id: str
    target_id: str
    payload: str


@dataclass(frozen=True)
class CompilationRecords:
    objects: tuple[CompiledObject, ...]
    links: tuple[CompiledLink, ...]
