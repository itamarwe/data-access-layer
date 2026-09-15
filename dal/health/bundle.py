"""Read-only validation of the active immutable query bundle."""

import json
import re
from dal.compiler.integrity import verify_bundle
from .model import HealthIssue


def inspect_bundle(bundle, repository_revision, expected_objects=None):
    pointer_path = bundle.root / "active.json"
    try:
        revision = json.loads(pointer_path.read_text())["revision"]
        if not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{24}", revision):
            raise ValueError("invalid active revision")
        target = bundle.root / "revisions" / revision
        manifest = verify_bundle(target, revision)
    except (ValueError, OSError, KeyError, TypeError) as error:
        return [HealthIssue("BUNDLE_CORRUPT", str(pointer_path), str(error),
            "dal build --help  # select a new --output directory to rebuild corrupt derived data")]
    mismatched = (
        (expected_objects is not None and manifest.get("object_hashes") != expected_objects)
        or (bundle.expected_revision is not None and revision != bundle.expected_revision)
    )
    if mismatched:
        return [HealthIssue("ACTIVE_REVISION_MISMATCH", str(target),
            "The compiled objects do not match the current resource files or expected revision.", "dal build")]
    return []
