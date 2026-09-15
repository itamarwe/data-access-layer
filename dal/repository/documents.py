"""Deterministic authored-document I/O."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from dal.documents import dump_document, load_document


def read_document(path: Path) -> dict[str, object]:
    return load_document(path.read_text(encoding="utf-8"), _format(path))


def encode_document(path: Path, document: Mapping[str, object]) -> str:
    return dump_document(document, _format(path))


def semantic_path(root: Path, relative: str) -> Path:
    """Resolve an authored semantic path without allowing traversal or symlinks."""
    candidate = PurePosixPath(relative)
    if (
        candidate.is_absolute()
        or not candidate.parts
        or candidate.parts[0] != "semantic"
        or ".." in candidate.parts
        or candidate.suffix.lower() not in {".json", ".yaml", ".yml"}
    ):
        raise ValueError(f"invalid semantic document path: {relative!r}")
    resolved_root = root.resolve()
    resolved = (root / Path(*candidate.parts)).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise ValueError(f"semantic document leaves repository: {relative!r}")
    return resolved


def _format(path: Path) -> str:
    return "json" if path.suffix.lower() == ".json" else "yaml"


def load_repository(root: Path | str) -> dict:
    from dal.model import require_valid
    document = {"version": 1, "objects": []}
    for path in semantic_files(Path(root)):
        value = read_document(path)
        if value.get("version") != 1 or not isinstance(value.get("objects"), list) or set(value) - {"version", "objects"}:
            raise ValueError(f"invalid native context file: {path}")
        document["objects"].extend(value["objects"])
    require_valid(document)
    document["objects"].sort(key=lambda item: item["id"])
    return document


def semantic_files(root: Path) -> tuple[Path, ...]:
    directory = root / "semantic"
    return tuple(sorted(path for path in directory.rglob("*") if path.is_file()
                        and not path.is_symlink() and path.suffix.lower() in {".json", ".yaml", ".yml"}))
