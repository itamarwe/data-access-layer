"""Development retrieval regression; object IDs do not establish SQL correctness."""

from pathlib import Path

from dal.application import BundleCatalog, CatalogService, SearchOptions
from dal.compiler import BundleBuilder
from dal.evaluation import CatalogSearchAdapter, assess_gate, evaluate, load_case_set

from .synthetic_catalog import synthetic_document

HERE = Path(__file__).parent


def test_synthetic_cases_retrieve_expected_objects_within_budget(tmp_path):
    cases = load_case_set(HERE / "synthetic_cases.json")
    bundle = BundleBuilder(tmp_path / "bundle").build(synthetic_document()).bundle
    adapter = CatalogSearchAdapter(CatalogService(BundleCatalog(bundle)),
                                   options=SearchOptions(max_details=8, max_compact=20))
    run = evaluate("synthetic-development-retrieval", cases.evaluable_cases, adapter)
    assert run.evaluation_type == "retrieval_regression"
    assert assess_gate(run, cases.gate).meets_gate


def test_synthetic_case_references_resolve_to_fixture_objects():
    cases = load_case_set(HERE / "synthetic_cases.json")
    identifiers = {item["id"] for item in synthetic_document()["objects"]}
    assert len(cases.cases) == 5
    assert cases.source["split"] == "development"
    assert cases.source["synthetic"] is True
    for case in cases.cases:
        assert case.expected_object_ids <= identifiers
        assert case.source_refs
        for reference in case.source_refs:
            filename, identifier = reference.split("#", 1)
            assert (HERE / filename).is_file()
            assert identifier in identifiers
