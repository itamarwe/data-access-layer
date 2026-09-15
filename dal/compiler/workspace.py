"""Resumable workspaces and atomic revision activation."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path


def prepare_workspace(root: Path, revision: str, base: Path | None) -> Path:
    work = root / ".builds" / revision
    state = work / "build-state.json"
    work.mkdir(parents=True, exist_ok=True)
    database = work / "catalog.duckdb"
    # Interrupted transactions restart from the immutable base. Never trust a
    # partial database merely because its state marker survived.
    database.unlink(missing_ok=True)
    database.with_suffix(".duckdb.wal").unlink(missing_ok=True)
    if base is not None and (base / "catalog.duckdb").is_file():
        shutil.copy2(base / "catalog.duckdb", database)
    write_json_atomic(state, {
        "revision": revision,
        "base_revision": base.name if base is not None else None,
    })
    return work


def workspace_base(root: Path, revision: str, active: Path | None) -> Path | None:
    state = root / ".builds" / revision / "build-state.json"
    if not state.is_file():
        return active
    base_revision = json.loads(state.read_text())["base_revision"]
    if base_revision is None:
        return None
    if not isinstance(base_revision, str) or len(base_revision) != 24 or any(char not in "0123456789abcdef" for char in base_revision):
        raise ValueError("invalid build base revision")
    base = root / "revisions" / base_revision
    from .integrity import verify_bundle
    verify_bundle(base, base_revision)
    return base


def publish_workspace(work: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.rename(work, target)
    except OSError:
        if not target.is_dir():
            raise
        _same_revision(target, work.name)
        shutil.rmtree(work)
    _sync_directory(target.parent)


def activate_revision(root: Path, revision: str) -> None:
    from .integrity import verify_bundle
    if not isinstance(revision, str) or len(revision) != 24 or any(char not in "0123456789abcdef" for char in revision):
        raise ValueError("invalid bundle revision")
    verify_bundle(root / "revisions" / revision, revision)
    write_json_atomic(root / "active.json", {"revision": revision})


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _same_revision(target: Path, revision: str) -> None:
    manifest = json.loads((target / "manifest.json").read_text())
    if manifest.get("revision") != revision:
        raise RuntimeError(f"revision directory collision: {revision}")


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
