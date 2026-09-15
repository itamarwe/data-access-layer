"""Safe, deterministic native JSON/YAML transport."""

import json
from collections.abc import Mapping

import yaml


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if not isinstance(key, str) or key in result:
            raise ValueError(f"duplicate or non-text document key: {key!r}")
        result[key] = value
    return result


class _Loader(yaml.SafeLoader):
    pass


def _mapping(loader, node):
    return _unique((loader.construct_object(k), loader.construct_object(v)) for k, v in node.value)


_Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_document(text: str, format: str = "yaml") -> dict:
    try:
        value = json.loads(text, object_pairs_hook=_unique) if format == "json" else yaml.load(text, Loader=_Loader)
        if not isinstance(value, dict):
            raise ValueError("document must be a mapping")
        canonical_json(value)
        return value
    except (yaml.YAMLError, TypeError, RecursionError) as error:
        raise ValueError(f"invalid document: {error}") from error


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def dump_document(value: Mapping, format: str = "yaml") -> str:
    canonical_json(value)
    if format == "json":
        return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    return yaml.safe_dump(dict(value), sort_keys=True, allow_unicode=True)
