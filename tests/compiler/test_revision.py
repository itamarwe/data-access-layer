import dal.compiler.revision as revision_module
from dal.compiler.revision import bundle_revision

from .fixtures import native_document


def test_compiler_version_affects_revision(monkeypatch):
    original = bundle_revision(native_document(), b"evidence", None)
    monkeypatch.setattr(revision_module, "COMPILER_VERSION", "next-compiler")
    assert bundle_revision(native_document(), b"evidence", None) != original


def test_evidence_content_affects_revision():
    assert bundle_revision(native_document(), b"first", None) != bundle_revision(native_document(), b"second", None)


def test_dictionary_key_order_does_not_affect_revision():
    document = native_document()
    reordered = {key: document[key] for key in reversed(document)}
    assert bundle_revision(document, b"evidence", None) == bundle_revision(reordered, b"evidence", None)


def test_resource_order_does_not_affect_revision():
    document = native_document()
    reordered = {"version": 1, "objects": list(reversed(document["objects"]))}
    assert bundle_revision(document, b"evidence", None) == bundle_revision(reordered, b"evidence", None)
