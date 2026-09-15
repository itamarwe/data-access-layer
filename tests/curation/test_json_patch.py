from __future__ import annotations

import pytest

from dal.curation import CurationError, apply_patch


def test_patch_is_side_effect_free_and_supports_the_explicit_subset():
    original = {"items": [{"name": "old"}], "remove_me": True}
    patched = apply_patch(original, [
        {"op": "replace", "path": "/items/0/name", "value": "new"},
        {"op": "add", "path": "/items/-", "value": {"name": "second"}},
        {"op": "remove", "path": "/remove_me"},
    ])

    assert original == {"items": [{"name": "old"}], "remove_me": True}
    assert patched == {"items": [{"name": "new"}, {"name": "second"}]}


@pytest.mark.parametrize("operation", [
    {"op": "move", "path": "/a"},
    {"op": "replace", "path": "relative", "value": 1},
    {"op": "remove", "path": "/missing"},
    {"op": "add", "path": "/array/3", "value": 1},
    {"op": "replace", "path": "/a~2b", "value": 1},
])
def test_unsafe_or_invalid_patch_operations_fail(operation):
    with pytest.raises(CurationError):
        apply_patch({"a": 1, "array": []}, [operation])


def test_json_pointer_escaping_is_honored():
    patched = apply_patch({"a/b": {"~key": 1}}, [
        {"op": "replace", "path": "/a~1b/~0key", "value": 2},
    ])

    assert patched == {"a/b": {"~key": 2}}
