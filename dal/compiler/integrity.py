"""Validate immutable artifacts before activation or cache reuse."""

import hashlib
import json
from pathlib import Path

import duckdb

from dal.database import read_only_connection


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_bundle(path: Path, revision: str | None = None) -> dict:
    from .constants import BUNDLE_FORMAT, COMPILER_VERSION
    try:
        manifest = json.loads((path / "manifest.json").read_text())
        if (manifest.get("format") != BUNDLE_FORMAT or manifest.get("compiler_version") != COMPILER_VERSION
                or (revision is not None and manifest.get("revision") != revision)):
            raise ValueError("bundle revision or format does not match")
        checksums = manifest.get("files", {})
        for name in ("catalog.duckdb", "evidence.json"):
            if checksums.get(name) != file_digest(path / name):
                raise ValueError(f"bundle checksum mismatch: {name}")
        with read_only_connection(path / "catalog.duckdb") as db:
            actual = db.execute("SELECT value FROM meta WHERE key='revision'").fetchone()
            if actual is None or actual[0] != manifest["revision"]:
                raise ValueError("database revision mismatch")
            for table in ("objects", "links", "terms", "evidence", "embeddings", "bm25_terms", "bm25_corpus"):
                db.execute(f"SELECT * FROM {table} LIMIT 0")
            actual_hashes = dict(db.execute("SELECT id, content_hash FROM objects").fetchall())
            if actual_hashes != manifest.get("object_hashes") or len(actual_hashes) != manifest.get("object_count"):
                raise ValueError("database objects do not match manifest")
            for table, key in (("links", "link_count"), ("evidence", "evidence_count")):
                if db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] != manifest.get(key):
                    raise ValueError(f"database {table} count does not match manifest")
            if checksums["evidence.json"] != manifest.get("evidence_sha256"):
                raise ValueError("evidence snapshot does not match build input")
        return manifest
    except (OSError, KeyError, TypeError, json.JSONDecodeError, duckdb.Error) as error:
        raise ValueError(f"corrupt bundle {path.name}: {error}") from error
