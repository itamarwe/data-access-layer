import json

from dal.cli.main import main
from dal.documents import dump_document
from tests.application.fixtures import native_document
from tests.health.helpers import NOW, authored_repository


def test_build_is_idempotent_and_keeps_source_immutable(tmp_path, capsys):
    source = tmp_path / "catalog.yaml"
    source.write_text(dump_document(native_document()), encoding="utf-8")
    original = source.read_bytes()
    output = tmp_path / "bundle"

    assert main(["build", str(source), "--output", str(output)]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["reused"] is False

    assert main(["build", str(source), "--output", str(output)]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["revision"] == first["revision"]
    assert second["reused"] is True
    assert source.read_bytes() == original


def test_health_uses_only_explicit_local_inputs(tmp_path, capsys):
    canonical, _ = authored_repository(tmp_path)
    snapshot = tmp_path / "physical.json"
    snapshot.write_text(json.dumps({
        "tables": [
            {
                "source": "warehouse.sales.orders",
                "columns": {"order_id": "INTEGER", "customer_id": "INTEGER"},
                "data_updated_at": NOW.isoformat(),
            },
            {
                "source": "warehouse.sales.customers",
                "columns": {"customer_id": "INTEGER", "email": "STRING"},
                "data_updated_at": NOW.isoformat(),
            },
        ],
    }), encoding="utf-8")
    snapshot_before = snapshot.read_bytes()
    canonical_before = canonical.read_bytes()

    code = main([
        "health", "--repository", str(tmp_path), "--now", NOW.isoformat(),
        "--physical-catalog", str(snapshot),
    ])

    result = json.loads(capsys.readouterr().out)
    assert code in (0, 1)
    assert set(result) == {"failures", "gaps", "checks"}
    assert snapshot.read_bytes() == snapshot_before
    assert canonical.read_bytes() == canonical_before


def test_health_failure_is_not_reported_as_success(tmp_path, capsys):
    code = main([
        "health", "--repository", str(tmp_path), "--now", NOW.isoformat(),
    ])

    result = json.loads(capsys.readouterr().out)
    assert code == 1
    assert result["failures"]


def test_build_accepts_explicit_local_embedding_model(tmp_path, capsys, monkeypatch):
    from dal.cli import build_commands
    from tests.application.test_search_signals import FixedEmbedder

    requested = []
    monkeypatch.setattr(build_commands, "_embedder", lambda model: requested.append(model) or FixedEmbedder())
    source = tmp_path / "catalog.yaml"
    source.write_text(dump_document(native_document()))
    assert main(["build", str(source), "--output", str(tmp_path / "bundle"),
                 "--embedding-model", "local-test-model"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert requested == ["local-test-model"]
    assert result["bundle"]
