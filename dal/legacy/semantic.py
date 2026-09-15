"""Preserve archive ontology, methodology, and curated queries as native objects."""

import re
from collections.abc import Mapping
from copy import deepcopy

from dal.identity import stable_id


def enrich_document(document, *, model_name, entity_definitions, relation_names,
                    curated_questions, query_cookbook=None, source_revision=None):
    result = deepcopy(dict(document))
    objects = result["objects"]
    definitions = {str(name): value for name, value in entity_definitions.items()
                   if name != "_domain" and isinstance(value, Mapping)}
    parsed = []
    for source, description in sorted(relation_names.items()):
        match = re.match(r"^(.*?):\s*([A-Z_]+)\.([^ ]+)\s+~\s+([A-Z_]+)\.(.+)$", str(source))
        if match and isinstance(description, str) and description.strip():
            parsed.append((match[2], match[4], description.strip()))
    entity_names = set(definitions) | {name for left, right, _ in parsed for name in (left, right)}
    replacements = {stable_id("property", name): stable_id("entity", name) for name in entity_names}
    bindings = {replacements[item["id"]]: item.get("bindings", [])
                for item in objects if item["id"] in replacements}
    objects[:] = [item for item in objects if item["id"] not in replacements]
    for item in objects:
        if "bindings" in item:
            item["bindings"] = [replacements.get(value, value) for value in item["bindings"]]
    for name in sorted(entity_names):
        definition = definitions.get(name, {})
        description = " ".join(str(definition[key]).strip() for key in ("definition", "identified_by", "not_to_be_confused_with", "roles")
                               if definition.get(key))
        item = {"id": stable_id("entity", name), "kind": "entity", "name": name}
        if bindings.get(item["id"]):
            item["bindings"] = bindings[item["id"]]
        if description:
            item["description"] = description
        if definition.get("noun"):
            item["aliases"] = [str(definition["noun"])]
        objects.append(item)
    seen = set()
    for left, right, description in parsed:
        natural_key = f"{left}:{right}:{description}"
        if natural_key in seen:
            continue
        seen.add(natural_key)
        objects.append({
            "id": stable_id("relation", natural_key), "kind": "relation", "name": description,
            "description": description, "from_id": stable_id("entity", left),
            "to_id": stable_id("entity", right),
        })
    domain = entity_definitions.get("_domain", {})
    parts = [str(domain[key]).strip() for key in ("summary", "caution") if isinstance(domain, Mapping) and domain.get(key)]
    if query_cookbook and query_cookbook.strip():
        parts.append(query_cookbook.strip())
    if parts:
        objects.append({
            "id": stable_id("doctrine", f"{model_name}:query-methodology"),
            "kind": "doctrine", "name": str(domain.get("title") or f"{model_name} query methodology"),
            "content": "\n\n".join(parts),
        })
    tables = {item["source"]: item["id"] for item in objects if item["kind"] == "table"}
    for source_id, value in sorted(curated_questions.items()):
        if not isinstance(value, Mapping) or value.get("speculative"):
            continue
        question, sql = value.get("question"), value.get("sql")
        if not isinstance(question, str) or not question.strip() or not isinstance(sql, str) or not sql.strip():
            continue
        item = {
            "id": stable_id("gold_query", str(source_id)), "kind": "gold_query",
            "name": question.strip(), "question": question.strip(), "sql": sql, "dialect": "athena",
            "object_ids": sorted(identifier for source, identifier in tables.items()
                                 if source in {entry.get("table") for entry in value.get("tables", []) if isinstance(entry, Mapping)}
                                 or re.search(rf"(?<![A-Za-z0-9_]){re.escape(source)}(?![A-Za-z0-9_])", sql, re.I)),
            **({"curation": {"source_revision": source_revision}} if source_revision else {}),
        }
        if value.get("parameters"):
            item["parameters"] = deepcopy(value["parameters"])
        if value.get("notes"):
            item["description"] = str(value["notes"])
        objects.append(item)
    return result
