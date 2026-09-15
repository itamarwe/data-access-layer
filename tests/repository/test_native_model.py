import pytest

from dal.model import validate_document
from dal.repository import load_repository
from dal.documents import dump_document, load_document


@pytest.mark.parametrize("resource", [
    {"id": "t", "kind": "table", "name": "t", "curation": []},
    {"id": "t", "kind": "table", "name": "t", "status": []},
    {"id": "t", "kind": "table", "name": "t", "restricted": "false"},
    {"id": "t", "kind": "table", "name": "t", "grain": {"known": False}},
])
def test_bad_optional_values_return_diagnostics(resource):
    assert validate_document({"version": 1, "objects": [resource]})


def test_duplicate_keys_and_nonfinite_json_rejected():
    for text in ('{"version":1,"version":1,"objects":[]}', '{"version":1,"objects":[],"bad":NaN}'):
        with pytest.raises(ValueError):
            load_document(text, "json")


def test_direct_file_changes_are_the_store(tmp_path):
    path = tmp_path / "semantic" / "catalog.yaml"
    path.parent.mkdir()
    document = {"version": 1, "objects": [{"id": "t", "kind": "table", "name": "before"}]}
    path.write_text(dump_document(document))
    assert load_repository(tmp_path)["objects"][0]["name"] == "before"
    document["objects"][0]["name"] = "after"
    path.write_text(dump_document(document))
    assert load_repository(tmp_path)["objects"][0]["name"] == "after"
