from dal.application import BundleCatalog, CatalogService
from dal.compiler import BundleBuilder
from dal.evaluation import CatalogSearchAdapter, EvaluationCase, evaluate


class FixedCounter:
    def count(self, _text):
        return 7


def test_retrieval_costs_and_explicit_evaluation_type(tmp_path):
    document = {"version": 1, "objects": [
        {"id": "table:orders", "kind": "table", "name": "orders"},
    ]}
    catalog = CatalogService(BundleCatalog(BundleBuilder(tmp_path / "bundle").build(document).bundle))
    clock = iter((100.0, 112.5))
    adapter = CatalogSearchAdapter(catalog, token_counter=FixedCounter(), clock_ms=lambda: next(clock))
    run = evaluate("lexical", [EvaluationCase("orders", "orders", frozenset({"table:orders"}), 1, 2000)], adapter)
    result = run.results[0]
    assert run.evaluation_type == "retrieval_regression"
    assert result.success_at_budget
    assert (result.turns, result.input_tokens, result.output_tokens, result.latency_ms) == (1, 7, 7, 12.5)
    assert not result.embedding_available


def test_incidental_relationship_endpoints_do_not_count_as_retrieval():
    from types import SimpleNamespace
    from dal.evaluation.catalog_adapter import _response_ids
    response = SimpleNamespace(
        results=(), also_matched=(), start_with=None, relevant_doctrine=None, relevant_gold_query=None,
        relationships=(SimpleNamespace(id="join:1", source_id="table:orders", target_id="table:customers"),),
    )
    assert _response_ids(response) == ()
