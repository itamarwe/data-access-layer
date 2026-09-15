"""Local bundle compilation command."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from dal.compiler import BundleBuilder
from dal.evidence import deserialize_snapshot, SnapshotRepository
from dal.repository import load_repository, semantic_files, replace_texts, repository_lock, encode_document
from dal.documents import dump_document, load_document

from .contracts import CommandOutcome
from .files import read_document


def register(commands) -> None:
    build = commands.add_parser("build", help="Validate and compile the native catalog files.")
    build.add_argument("input", nargs="?", help="Optional standalone native catalog document.")
    build.add_argument("--output", help="Default: REPOSITORY/.dal/query.")
    build.add_argument("--refresh", type=Path, help="Collect a captured Glue/Athena JSON snapshot before building.")
    build.add_argument("--embedding-model", help="Build local embeddings using this fastembed model (may download model weights).")
    build.add_argument(
        "--evidence-snapshot", action="append", default=[],
        help="Immutable evidence snapshot; repeat to include multiple snapshots.",
    )
    build.set_defaults(handler=run)


def run(arguments: argparse.Namespace) -> CommandOutcome:
    root = Path(arguments.repository)
    if arguments.refresh:
        if arguments.input:
            raise ValueError("--refresh operates on repository files; omit the standalone input")
        _refresh(root, arguments.refresh)
    snapshots = tuple(Path(path) for path in arguments.evidence_snapshot) or tuple(sorted((root / "evidence").glob("*.json")))
    evidence = (
        snapshots[0] if len(snapshots) == 1
        else _merged_evidence(snapshots)
    )
    embedder = _embedder(arguments.embedding_model) if arguments.embedding_model else None
    result = BundleBuilder(Path(arguments.output) if arguments.output else Path(arguments.repository) / ".dal" / "query", embedder).build(
        read_document(arguments.input) if arguments.input else load_repository(Path(arguments.repository)), evidence,
    )
    return CommandOutcome(result)


def _embedder(model):
    from dal.compiler.embedding import FastEmbedder
    try:
        return FastEmbedder(model)
    except ImportError as error:
        raise ValueError("local embeddings require the fastembed dependency; install DAL with its embeddings extra") from error
    except StopIteration as error:
        raise ValueError(f"unsupported local embedding model: {model}") from error


def _merged_evidence(snapshots):
    records = {}
    for path in snapshots:
        for record in deserialize_snapshot(path.read_bytes()):
            previous = records.get(record.record_id)
            if previous is not None and replace(previous, collected_at=record.collected_at) != record:
                raise ValueError(f"conflicting evidence ID in snapshots: {record.record_id}")
            if previous is None or record.collected_at > previous.collected_at:
                records[record.record_id] = record
    return records.values()


def _refresh(root, source):
    from dal.collectors import collect_snapshot, refresh_document
    from dal.model import require_valid

    collected = collect_snapshot(source)
    with repository_lock(root):
        previous = load_repository(root)
        document = refresh_document(previous, collected.objects)
        require_valid(document)
        remaining = {item["id"]: item for item in document["objects"]}
        writes = {}
        for path in semantic_files(root):
            original = read_document(str(path))
            objects = [remaining.pop(item["id"]) for item in original["objects"]]
            writes[path] = encode_document(path, {"version": 1, "objects": objects})
        if remaining:
            path = root / "semantic" / "collected.yaml"
            current = load_document(writes[path])["objects"] if path in writes else []
            writes[path] = dump_document({"version": 1, "objects": current + list(remaining.values())})
        SnapshotRepository(root / "evidence").put(collected.evidence)
        replace_texts(writes)
