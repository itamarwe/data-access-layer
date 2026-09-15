import json

from dal.cli.main import build_parser, main
from dal.documents import dump_document
from tests.application.fixtures import native_document


def test_init_validate_build_search_work_with_repository_defaults(tmp_path, capsys):
    prefix = ["--repository", str(tmp_path)]
    assert main([*prefix, "init"]) == 0
    capsys.readouterr()
    catalog = tmp_path / "semantic" / "catalog.yaml"
    catalog.write_text(dump_document(native_document()))
    assert main([*prefix, "validate"]) == 0
    assert json.loads(capsys.readouterr().out)["valid"]
    assert main([*prefix, "build"]) == 0
    capsys.readouterr()
    assert main([*prefix, "table", "search", "orders"]) == 0
    assert json.loads(capsys.readouterr().out)["results"][0]["object"]["name"] == "orders"


def test_invalid_native_catalog_reports_diagnostics(tmp_path, capsys):
    source = tmp_path / "bad.json"
    source.write_text('{"version": 1, "objects": [{"id": "x", "kind": "table"}]}')
    assert main(["validate", str(source)]) == 1
    assert json.loads(capsys.readouterr().out)["diagnostics"]


def test_no_ossie_command_is_exposed():
    assert "ossie" not in build_parser().format_help().lower()
