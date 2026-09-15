from dal.compiler import BundleBuilder
from dal.documents import dump_document
from dal.health import ActiveBundle, inspect_health
from .helpers import authored_repository, request


def test_healthy_bundle_and_direct_edit_staleness(tmp_path):
    path, document = authored_repository(tmp_path)
    bundle = tmp_path / ".dal"
    BundleBuilder(bundle).build(document)
    assert inspect_health(request(tmp_path, active_bundle=ActiveBundle(bundle))).healthy
    document["objects"][0]["description"] = "Different meaning"
    path.write_text(dump_document(document))
    result = inspect_health(request(tmp_path, active_bundle=ActiveBundle(bundle)))
    assert "ACTIVE_REVISION_MISMATCH" in {x.code for x in result.failures}


def test_corrupt_cached_artifact_is_reported(tmp_path):
    _, document = authored_repository(tmp_path)
    bundle = tmp_path / ".dal"
    built = BundleBuilder(bundle).build(document)
    (built.bundle / "evidence.json").write_text("{}")
    result = inspect_health(request(tmp_path, active_bundle=ActiveBundle(bundle)))
    assert "BUNDLE_CORRUPT" in {x.code for x in result.failures}


def test_malicious_pointer_is_rejected(tmp_path):
    authored_repository(tmp_path)
    bundle = tmp_path / ".dal"
    bundle.mkdir()
    (bundle / "active.json").write_text('{"revision":"../../outside"}')
    result = inspect_health(request(tmp_path, active_bundle=ActiveBundle(bundle)))
    assert "BUNDLE_CORRUPT" in {x.code for x in result.failures}
