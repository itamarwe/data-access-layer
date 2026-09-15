from dal.health import inspect_health
from dal.documents import dump_document
from .helpers import authored_repository, request


def test_missing_grain_is_a_gap_not_a_failure(tmp_path):
    authored_repository(tmp_path)
    result = inspect_health(request(tmp_path))
    assert result.healthy
    assert "GRAIN_MISSING" in {gap.code for gap in result.gaps}
    assert {check["name"] for check in result.checks if not check["performed"]} == {"physical", "evidence", "bundle"}


def test_corrupt_files_and_unresolved_references_are_failures(tmp_path):
    path, document = authored_repository(tmp_path)
    document["objects"][2]["parent_id"] = "table:missing"
    path.write_text(dump_document(document))
    assert not inspect_health(request(tmp_path)).healthy
    path.write_text("objects: [")
    assert "FILE_CORRUPT" in {x.code for x in inspect_health(request(tmp_path)).failures}


def test_duplicate_yaml_keys_are_not_silently_accepted(tmp_path):
    path, _ = authored_repository(tmp_path)
    path.write_text("version: 1\nversion: 2\nobjects: []\n")
    assert not inspect_health(request(tmp_path)).healthy


def test_empty_repository_has_recovery(tmp_path):
    result = inspect_health(request(tmp_path))
    assert result.failures[0].recovery_command == "dal init"


def test_cross_file_references_are_valid(tmp_path):
    path, document = authored_repository(tmp_path)
    path.write_text(dump_document({"version": 1, "objects": document["objects"][:2]}))
    path.with_name("other.yaml").write_text(dump_document({"version": 1, "objects": document["objects"][2:]}))
    assert inspect_health(request(tmp_path)).healthy
