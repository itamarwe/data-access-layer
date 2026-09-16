from dataclasses import replace
from pathlib import Path

from dal.application import BundleCatalog, CatalogService
from dal.compiler import BundleBuilder
from dal.evaluation import CatalogSearchAdapter, evaluate, load_case_set
from .multipart import run
from .synthetic_catalog import synthetic_document


def test_multipart_fact_retrieval_covers_all_requirements_and_counts_cost(tmp_path):
    report = run(tmp_path)
    results = report["fact_by_fact"]["results"]
    assert len(results) == 2
    assert all(item["success"] and item["within_budget"] for item in results)
    assert all(item["turns"] == 3 and item["input_tokens"] > 0 and item["output_tokens"] > 0 for item in results)


def test_missing_one_required_fact_fails_even_if_other_facts_match(tmp_path):
    document = synthetic_document()
    document["objects"] = [item for item in document["objects"] if item["id"] != "column:members.email"]
    bundle = BundleBuilder(tmp_path / "bundle").build(document)
    cases = load_case_set(Path(__file__).with_name("multipart_cases.json"))
    adapter = CatalogSearchAdapter(CatalogService(BundleCatalog(bundle.bundle)))
    result = evaluate("missing-email", cases.cases[:1], adapter).results[0]
    assert not result.success
    assert result.recall < 1


def test_fact_plan_cannot_hide_extra_turns(tmp_path):
    bundle = BundleBuilder(tmp_path / "bundle").build(synthetic_document())
    case = load_case_set(Path(__file__).with_name("multipart_cases.json")).cases[0]
    adapter = CatalogSearchAdapter(CatalogService(BundleCatalog(bundle.bundle)))
    result = evaluate("tight-turn-budget", [replace(case, max_turns=1)], adapter).results[0]
    assert result.success
    assert not result.within_budget
