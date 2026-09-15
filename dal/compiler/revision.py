"""Content identity independent of serialization and object order."""

import hashlib
from dal.documents import canonical_json
from dal.model import VERSION
from .constants import BUNDLE_FORMAT, COMPILER_VERSION
from .embedding import embedding_health


def bundle_revision(document, evidence_payload, embedder):
    contract = {"format": BUNDLE_FORMAT, "compiler": COMPILER_VERSION,
                "model_version": VERSION, "embedding": embedding_health(embedder)}
    normalized = {"version": VERSION, "objects": sorted(document["objects"], key=lambda item: item["id"])}
    digest = hashlib.sha256()
    for payload in (canonical_json(contract), canonical_json(normalized), evidence_payload):
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()[:24]
