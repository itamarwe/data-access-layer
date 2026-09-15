import json

from dal.cli.main import main
from dal.documents import dump_document
from dal.repository import repository_revision
from tests.curation.helpers import proposal, repository


def _proposal_file(path, value):
    path.write_text(dump_document(value), encoding="utf-8")
    return path


def test_proposal_create_list_get_and_publish_use_curation_service(tmp_path, capsys):
    canonical = repository(tmp_path)
    original = canonical.read_bytes()
    revision = repository_revision(tmp_path)
    value = proposal(tmp_path)
    source = _proposal_file(tmp_path / "candidate.yaml", value)

    assert main([
        "proposal", "--repository", str(tmp_path), "create", str(source),
        "--expected-revision", revision,
    ]) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["proposal"]["status"] == "open"
    assert canonical.read_bytes() == original

    assert main([
        "proposal", "--repository", str(tmp_path), "list", "--status", "open",
    ]) == 0
    listing = json.loads(capsys.readouterr().out)
    assert [item["id"] for item in listing["proposals"]] == [value["id"]]
    repository_before_get = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*") if path.is_file()
    }

    assert main([
        "proposal", "--repository", str(tmp_path), "get", value["id"],
    ]) == 0
    found = json.loads(capsys.readouterr().out)
    assert found["proposal"]["id"] == value["id"]
    repository_after_get = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*") if path.is_file()
    }
    assert repository_after_get == repository_before_get

    assert main([
        "proposal", "--repository", str(tmp_path), "publish", value["id"],
        "--expected-revision", created["repository_revision"],
        "--decided-by", "user:reviewer",
    ]) == 0
    published = json.loads(capsys.readouterr().out)
    assert published["proposal"]["status"] == "published"
    assert canonical.read_bytes() != original


def test_revision_conflict_preserves_repository(tmp_path, capsys):
    canonical = repository(tmp_path)
    value = proposal(tmp_path)
    source = _proposal_file(tmp_path / "candidate.yaml", value)
    canonical_before = canonical.read_bytes()
    source_before = source.read_bytes()

    code = main([
        "proposal", "--repository", str(tmp_path), "create", str(source),
        "--expected-revision", "stale-revision",
    ])

    error = json.loads(capsys.readouterr().err)
    assert code == 2
    assert error["type"] == "RevisionConflict"
    assert canonical.read_bytes() == canonical_before
    assert source.read_bytes() == source_before
    assert not (tmp_path / "proposals").exists()


def test_dismiss_leaves_canonical_document_unchanged(tmp_path, capsys):
    canonical = repository(tmp_path)
    before = canonical.read_bytes()
    value = proposal(tmp_path)
    source = _proposal_file(tmp_path / "candidate.yaml", value)

    assert main([
        "proposal", "--repository", str(tmp_path), "create", str(source),
        "--expected-revision", repository_revision(tmp_path),
    ]) == 0
    created = json.loads(capsys.readouterr().out)
    assert main([
        "proposal", "--repository", str(tmp_path), "dismiss", value["id"],
        "--expected-revision", created["repository_revision"],
    ]) == 0
    dismissed = json.loads(capsys.readouterr().out)

    assert dismissed["proposal"]["status"] == "dismissed"
    assert canonical.read_bytes() == before


def test_deprecate_requires_and_applies_a_publication_transition(tmp_path, capsys):
    repository(tmp_path, published_table=True)
    value = proposal(
        tmp_path,
        proposal_id="urn:dal:proposal:deprecate-orders",
        patch=[{
            "op": "replace",
            "path": "/status",
            "value": "deprecated",
        }],
    )
    source = _proposal_file(tmp_path / "candidate.yaml", value)

    assert main([
        "proposal", "--repository", str(tmp_path), "create", str(source),
        "--expected-revision", repository_revision(tmp_path),
    ]) == 0
    created = json.loads(capsys.readouterr().out)
    assert main([
        "proposal", "--repository", str(tmp_path), "deprecate", value["id"],
        "--expected-revision", created["repository_revision"],
    ]) == 0
    deprecated = json.loads(capsys.readouterr().out)

    assert deprecated["proposal"]["status"] == "published"
