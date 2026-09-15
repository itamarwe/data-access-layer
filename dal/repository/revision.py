"""Content identity for the authored, Git-controlled repository state."""

from __future__ import annotations

import hashlib
from pathlib import Path

AUTHORED_DIRECTORIES = ("config", "proposals", "schemas", "semantic")
AUTHORED_SUFFIXES = frozenset({".json", ".yaml", ".yml"})


def repository_revision(root: Path | str) -> str:
    """Hash authored paths and bytes without invoking Git."""
    repository = Path(root)
    digest = hashlib.sha256(b"dal-repository-v1\0")
    for path in _authored_files(repository):
        relative = path.relative_to(repository).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return f"sha256:{digest.hexdigest()}"


def require_revision(root: Path | str, expected: str) -> None:
    actual = repository_revision(root)
    if actual != expected:
        from .errors import RevisionConflict

        raise RevisionConflict(
            f"repository revision changed: expected {expected}, found {actual}",
        )


def _authored_files(root: Path) -> list[Path]:
    files = []
    for directory_name in AUTHORED_DIRECTORIES:
        directory = root / directory_name
        if not directory.is_dir():
            continue
        files.extend(
            path for path in directory.rglob("*")
            if path.is_file() and not path.is_symlink()
            and path.suffix.lower() in AUTHORED_SUFFIXES
        )
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())
