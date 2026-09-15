from __future__ import annotations

from pathlib import Path

import pytest

from dal.repository import RevisionConflict, repository_revision, require_revision, semantic_path


def test_revision_is_a_deterministic_hash_of_authored_content(tmp_path):
    semantic = tmp_path / "semantic"
    semantic.mkdir()
    document = semantic / "sales.ossie.yaml"
    document.write_text("version: 1\n", encoding="utf-8")
    first = repository_revision(tmp_path)

    document.touch()
    assert repository_revision(tmp_path) == first

    document.write_text("version: 2\n", encoding="utf-8")
    assert repository_revision(tmp_path) != first


def test_generated_bundle_does_not_change_repository_revision(tmp_path):
    before = repository_revision(tmp_path)
    generated = tmp_path / ".dal" / "revisions" / "one"
    generated.mkdir(parents=True)
    (generated / "graph.duckdb").write_bytes(b"generated")

    assert repository_revision(tmp_path) == before


def test_expected_revision_conflict_is_explicit(tmp_path):
    with pytest.raises(RevisionConflict, match="expected sha256:stale"):
        require_revision(tmp_path, "sha256:stale")


@pytest.mark.parametrize("relative", [
    "/tmp/model.yaml", "../model.yaml", "semantic/../../model.yaml",
    "config/model.yaml", "semantic/model.txt",
])
def test_semantic_path_rejects_paths_outside_the_contract(tmp_path, relative):
    with pytest.raises(ValueError, match="invalid semantic"):
        semantic_path(tmp_path, relative)
