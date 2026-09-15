"""Idempotent, resumable, incremental, and atomic bundle compilation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from dal.evidence import EvidenceRecord, serialize_snapshot
from dal.model import validate_document
from dal.repository.locking import repository_lock

from .constants import BUNDLE_FORMAT, COMPILER_VERSION
from .diagnostics import compilation_diagnostics
from .embedding import Embedder, embedding_health
from .extract import extract_records
from .revision import bundle_revision
from .integrity import file_digest, verify_bundle
from .storage import (
    open_writer, replace_evidence, replace_links, set_meta, update_embeddings,
    update_objects,
)
from .workspace import (
    activate_revision, prepare_workspace, publish_workspace, workspace_base,
    write_bytes_atomic, write_json_atomic,
)


@dataclass(frozen=True)
class BuildResult:
    revision: str
    bundle: Path
    reused: bool
    changed_objects: int
    removed_objects: int


class CompilationError(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = tuple(diagnostics)
        message = "; ".join(
            f"{item.pointer}: {item.message}" for item in diagnostics
        )
        super().__init__(message)


class BundleBuilder:
    def __init__(self, root: Path, embedder: Embedder | None = None):
        self.root = root
        self.embedder = embedder

    def build(
        self,
        document: Mapping[str, object],
        evidence: Iterable[EvidenceRecord] | Path = (),
    ) -> BuildResult:
        with repository_lock(self.root):
            return self._build(document, evidence)

    def _build(self, document, evidence) -> BuildResult:
        self._validate(document)
        records = extract_records(document)
        evidence_payload = (
            evidence.read_bytes() if isinstance(evidence, Path)
            else serialize_snapshot(evidence)
        )
        revision = bundle_revision(document, evidence_payload, self.embedder)
        target = self.root / "revisions" / revision
        if target.is_dir():
            verify_bundle(target, revision)
            activate_revision(self.root, revision)
            return BuildResult(revision, target, True, 0, 0)

        active = self._active_bundle()
        if active is not None and _manifest(active).get("compiler_version") != COMPILER_VERSION:
            active = None  # A compiler upgrade needs a fresh derived cache, not a file migration.
        if active is not None:
            verify_bundle(active, active.name)
        base = workspace_base(self.root, revision, active)
        old_manifest = _manifest(base)
        hashes = {
            item.object_id: _object_hash(item.payload) for item in records.objects
        }
        old_hashes = old_manifest.get("object_hashes", {})
        changed = {key for key, value in hashes.items() if old_hashes.get(key) != value}
        removed = set(old_hashes) - set(hashes)
        evidence_sha = hashlib.sha256(evidence_payload).hexdigest()
        links_sha = _links_hash(records.links)
        health = {"embeddings": embedding_health(self.embedder)}
        embedding_changed = old_manifest.get("health", {}).get("embeddings") != health["embeddings"]

        work = prepare_workspace(self.root, revision, base)
        evidence_path = work / "evidence.json"
        write_bytes_atomic(evidence_path, evidence_payload)
        del evidence_payload
        connection = open_writer(work / "catalog.duckdb")
        evidence_count = _previous_evidence_count(old_manifest)
        try:
            connection.execute("BEGIN TRANSACTION")
            update_objects(connection, records.objects, hashes, changed, removed)
            if old_manifest.get("links_sha256") != links_sha:
                replace_links(connection, records.links)
            if old_manifest.get("evidence_sha256") != evidence_sha:
                evidence_count = replace_evidence(connection, evidence_path)
            update_embeddings(
                connection, records.objects, changed, removed,
                self.embedder, embedding_changed,
            )
            set_meta(connection, {
                "bundle_format": BUNDLE_FORMAT,
                "compiler_version": COMPILER_VERSION,
                "embedding_health": json.dumps(health["embeddings"], sort_keys=True),
                "revision": revision,
            })
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

        manifest = {
            "compiler_version": COMPILER_VERSION,
            "evidence_count": evidence_count,
            "evidence_sha256": evidence_sha,
            "format": BUNDLE_FORMAT,
            "health": health,
            "link_count": len(records.links),
            "links_sha256": links_sha,
            "object_count": len(records.objects),
            "object_hashes": hashes,
            "revision": revision,
            "model_version": 1,
            "files": {"catalog.duckdb": file_digest(work / "catalog.duckdb"),
                      "evidence.json": file_digest(evidence_path)},
        }
        write_json_atomic(work / "manifest.json", manifest)
        publish_workspace(work, target)
        activate_revision(self.root, revision)
        return BuildResult(revision, target, False, len(changed), len(removed))

    @staticmethod
    def _validate(document: Mapping[str, object]) -> None:
        structural = validate_document(document)
        if structural:
            raise CompilationError(structural)
        semantic = compilation_diagnostics(document)
        if semantic:
            raise CompilationError(semantic)

    def _active_bundle(self) -> Path | None:
        pointer = self.root / "active.json"
        if not pointer.is_file():
            return None
        revision = json.loads(pointer.read_text())["revision"]
        if not isinstance(revision, str) or len(revision) != 24 or any(char not in "0123456789abcdef" for char in revision):
            raise ValueError("invalid active bundle revision")
        candidate = self.root / "revisions" / revision
        if not candidate.is_dir():
            raise ValueError("active bundle is missing; repair or remove active.json and rebuild")
        return candidate


def _object_hash(payload: str) -> str:
    value = f"{COMPILER_VERSION}\0{payload}".encode()
    return hashlib.sha256(value).hexdigest()


def _links_hash(links) -> str:
    payload = "\n".join(
        f"{item.link_id}\0{item.kind}\0{item.source_id}\0{item.target_id}\0{item.payload}"
        for item in links
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _manifest(bundle: Path | None) -> dict:
    if bundle is None:
        return {}
    return json.loads((bundle / "manifest.json").read_text())


def _previous_evidence_count(manifest: Mapping[str, object]) -> int:
    return int(manifest.get("evidence_count", 0))
