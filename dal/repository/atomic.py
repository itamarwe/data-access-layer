"""Atomic replacement of one or more authored files."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path


def replace_texts(changes: Mapping[Path, str]) -> None:
    """Replace a validated set of files and roll back ordinary I/O failures."""
    normalized = {Path(path): text for path, text in changes.items()}
    originals = {
        path: path.read_bytes() if path.exists() else None
        for path in normalized
    }
    staged = _stage({path: text.encode("utf-8") for path, text in normalized.items()})
    replaced = []
    try:
        for target in sorted(staged, key=lambda path: str(path)):
            os.replace(staged[target], target)
            replaced.append(target)
        _sync_directories(replaced)
    except BaseException:
        _rollback(replaced, originals)
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def _stage(changes: Mapping[Path, bytes]) -> dict[Path, Path]:
    staged = {}
    try:
        for target, content in changes.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                dir=target.parent, prefix=".dal-write-", suffix=".tmp",
            )
            temporary = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            staged[target] = temporary
    except BaseException:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
        raise
    return staged


def _rollback(replaced: list[Path], originals: Mapping[Path, bytes | None]) -> None:
    restore = {
        target: content for target in replaced
        if (content := originals[target]) is not None
    }
    for target in replaced:
        if originals[target] is None:
            target.unlink(missing_ok=True)
    staged = _stage(restore)
    for target, temporary in staged.items():
        os.replace(temporary, target)
    _sync_directories(replaced)


def _sync_directories(paths: list[Path]) -> None:
    for directory in sorted({path.parent for path in paths}, key=str):
        try:
            descriptor = os.open(directory, os.O_RDONLY)
        except OSError:
            continue
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
