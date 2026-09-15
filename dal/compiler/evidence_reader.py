"""Incrementally validate snapshot records before a build transaction commits."""

from pathlib import Path

from dal.evidence.serialization import snapshot_documents


def snapshot_records(path: Path):
    yield from snapshot_documents(path.read_text(encoding="utf-8"))
