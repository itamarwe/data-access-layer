"""Atomic filesystem repository for immutable evidence snapshots."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .model import EvidenceRecord
from .serialization import deserialize_snapshot, serialize_snapshot, snapshot_id


class SnapshotCollisionError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredSnapshot:
    snapshot_id: str
    path: Path
    record_count: int


class SnapshotRepository:
    def __init__(self, directory: Path):
        self.directory = directory

    def put(self, records: Iterable[EvidenceRecord]) -> StoredSnapshot:
        materialized = tuple(records)
        payload = serialize_snapshot(materialized)
        identifier = snapshot_id(payload)
        target = self.directory / f"{identifier}.json"
        self.directory.mkdir(parents=True, exist_ok=True)
        if target.exists():
            self._require_same_content(target, payload)
            return StoredSnapshot(identifier, target, len(materialized))
        self._publish(target, payload)
        return StoredSnapshot(identifier, target, len(materialized))

    def get(self, identifier: str) -> tuple[EvidenceRecord, ...]:
        if not isinstance(identifier, str) or re.fullmatch("[0-9a-f]{64}", identifier) is None:
            raise ValueError("snapshot ID must be 64 lowercase hexadecimal characters")
        payload = (self.directory / f"{identifier}.json").read_bytes()
        if snapshot_id(payload) != identifier:
            raise SnapshotCollisionError("snapshot content does not match its ID")
        return deserialize_snapshot(payload)

    @staticmethod
    def _require_same_content(target: Path, payload: bytes) -> None:
        if target.read_bytes() != payload:
            raise SnapshotCollisionError(f"snapshot digest collision: {target.stem}")

    def _publish(self, target: Path, payload: bytes) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".evidence-", suffix=".tmp", dir=self.directory,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.chmod(0o444)
            try:
                os.link(temporary, target)
            except FileExistsError:
                self._require_same_content(target, payload)
            self._sync_directory()
        finally:
            temporary.unlink(missing_ok=True)

    def _sync_directory(self) -> None:
        descriptor = os.open(self.directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
