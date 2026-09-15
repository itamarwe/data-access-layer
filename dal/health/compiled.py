"""Content identities expected in the compiled graph."""

from dal.compiler import extract_records
from dal.compiler.build import _object_hash


def expected_object_hashes(documents):
    document = {"version": 1, "objects": [item for doc in documents for item in doc.value["objects"]]}
    return {item.object_id: _object_hash(item.payload) for item in extract_records(document).objects}
