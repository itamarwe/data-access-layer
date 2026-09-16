import json

import pytest

from evals.context_graph import benchmark


def test_benchmark_report_and_file_match(tmp_path, capsys):
    output = tmp_path / "results" / "benchmark.json"
    assert benchmark.main(["--output", str(output)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert json.loads(output.read_text()) == report
    assert report["object_count"] == 17
    variant = report["variants"][0]
    assert variant["summary"]["cases"] == 5
    assert variant["summary"]["success_at_budget_rate"] == 1
    assert variant["embedding_model"] is None
    assert len(report["fixture_sha256"]) == 64
    assert all(result["latency_ms"] > 0 for result in variant["results"])


def test_failed_gate_returns_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(benchmark, "run_benchmark", lambda *args: {"variants": [{"gate_passed": False}]})
    assert benchmark.main([]) == 1
    assert json.loads(capsys.readouterr().out)["variants"][0]["gate_passed"] is False


def test_missing_hybrid_dependency_is_not_scored_as_bm25(monkeypatch, capsys):
    def unavailable(*args, **kwargs):
        raise ImportError("fastembed unavailable")
    monkeypatch.setattr(benchmark, "FastEmbedder", unavailable)
    with pytest.raises(SystemExit) as error:
        benchmark.main(["--search", "hybrid"])
    assert error.value.code == 2
    assert not capsys.readouterr().out


def test_invalid_budget_does_not_build():
    with pytest.raises(ValueError, match="at least 512"):
        benchmark.run_benchmark(tokens=0)
