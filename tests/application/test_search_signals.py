from datetime import datetime, timezone
from pathlib import Path
import pytest

from dal.application import BundleCatalog, CatalogService
from dal.compiler import BundleBuilder
from dal.evidence import ContentReference, EvidenceLayer, EvidenceRecord, EvidenceSource, SourceKind
from tests.application.fixtures import native_document


class FixedEmbedder:
    provider = "test"
    model_id = "fixed-2d"
    dimensions = 2

    def embed(self, texts):
        return ([1.0, 0.0] if "orders" in text or "purchase" in text else [0.0, 1.0]
                for text in texts)


def test_local_embedding_index_adds_semantic_candidates(tmp_path):
    result = BundleBuilder(tmp_path / "bundle", FixedEmbedder()).build(native_document())

    response = CatalogService(BundleCatalog(result.bundle), FixedEmbedder()).search_kind(
        "table", "purchase volume"
    )

    assert response.capabilities.embedding == "available"
    assert response.results[0].object.id == "urn:dal:table:orders"
    assert response.results[0].signals.embedding == 1.0


def test_evidence_is_ranked_and_returned_for_selected_context(tmp_path: Path):
    evidence = EvidenceRecord(
        record_id="urn:dal:evidence:orders-count",
        layer=EvidenceLayer.USAGE,
        subject_id="urn:dal:gold_query:orders",
        claim_path="/sql",
        claim_value="SELECT COUNT(*) FROM orders",
        source=EvidenceSource(SourceKind.QUERY_LOG, "2026-01"),
        collected_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        content=ContentReference("query-log://orders", "0" * 64),
        strength=0.9,
    )
    bundle = BundleBuilder(tmp_path / "bundle").build(native_document(), [evidence]).bundle

    response = CatalogService(BundleCatalog(bundle)).search("How many orders?")

    assert response.results[0].signals.evidence == 1.0
    assert response.evidence[0].layer == "usage"
    assert response.evidence[0].strength == 0.9
    assert response.evidence[0].claim_value == "SELECT COUNT(*) FROM orders"
    assert response.evidence[0].collected_at.startswith("2026-01-01")
    assert response.evidence[0].source_revision == "2026-01"


def test_weight_overrides_are_explicit_and_normalized(tmp_path):
    bundle = BundleBuilder(tmp_path / "bundle").build(native_document()).bundle
    response = CatalogService(BundleCatalog(bundle)).search(
        "orders", weights={"lexical": 1.0, "embedding": 0.0, "graph": 0.0,
                           "evidence": 0.0, "publication": 0.0},
    )

    assert response.ranking_weights.lexical == 1.0
    assert response.results[0].score == response.results[0].signals.lexical


def test_nonfinite_query_embeddings_are_rejected(tmp_path):
    class BrokenEmbedder(FixedEmbedder):
        def embed(self, texts):
            return [[float("nan"), 1.0] for _ in texts]

    bundle = BundleBuilder(tmp_path / "bundle", FixedEmbedder()).build(native_document()).bundle
    with pytest.raises(ValueError, match="non-finite"):
        CatalogService(BundleCatalog(bundle), BrokenEmbedder()).search("orders")
