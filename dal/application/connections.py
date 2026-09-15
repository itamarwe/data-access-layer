"""Domain connections are distinct from resource membership and references."""

import json

from dal.identity import stable_id
from .models import Connection, Connections, GraphNeighbor
from .presentation import summary


def connections(catalog, identifiers, limit):
    if not identifiers or limit == 0:
        return Connections()
    # Collapse compiler adjacency rows before applying the public result limit.
    with catalog._open() as db:
        rows = db.execute(
            "SELECT DISTINCT CASE WHEN kind IN ('join_column', 'join_table') THEN 'join' ELSE kind END AS category, "
            "CASE WHEN kind = 'ontology_binding' THEN target_id ELSE '' END AS mapped_target, payload "
            "FROM links WHERE kind IN ('relation', 'ontology_binding', 'join_column', 'join_table') "
            "AND (source_id IN (SELECT UNNEST(?)) OR target_id IN (SELECT UNNEST(?)) "
            "OR json_extract_string(payload, '$.id') IN (SELECT UNNEST(?))) "
            "AND coalesce(json_extract_string(payload, '$.status'), 'published') != 'deprecated' "
            "ORDER BY category, mapped_target, payload LIMIT ?",
            [list(identifiers), list(identifiers), list(identifiers), limit],
        ).fetchall()
    result = {"relations": [], "joins": [], "mappings": []}
    endpoint_ids = set()
    for category, target, payload in rows:
        item = json.loads(payload) if isinstance(payload, str) else payload
        if category == "join":
            endpoint_ids.update(item["left"] + item["right"])
    columns = catalog.objects(endpoint_ids)
    for category, target, payload in rows:
        item = json.loads(payload) if isinstance(payload, str) else payload
        if category == "relation":
            details = {key: item[key] for key in ("cardinality", "bindings") if key in item}
            result["relations"].append(Connection(item["id"], item["name"], item["from_id"], item["to_id"], details or None))
        elif category == "join":
            details = {key: item[key] for key in ("left", "right", "predicate", "cardinality", "join_type", "required_filters", "grain_effect") if key in item}
            result["joins"].append(Connection(item["id"], item["name"],
                columns[item["left"][0]].parent_id, columns[item["right"][0]].parent_id, details))
        else:
            result["mappings"].append(Connection(stable_id("mapping", f"{item['id']}:{target}"),
                "maps to", item["id"], target))
    return Connections(**{key: tuple(value) for key, value in result.items()})


def neighbors(catalog, object_id, limit):
    # Navigation returns native resources, never compiler edge types. Relations
    # themselves are reachable so their name, evidence and mappings can be read.
    with catalog._open() as db:
        rows = db.execute(
            "SELECT DISTINCT CASE WHEN source_id = ? THEN target_id ELSE source_id END AS neighbor_id, "
            "CASE kind "
            "WHEN 'contains' THEN CASE WHEN source_id = ? THEN 'children' ELSE 'parent_id' END "
            "WHEN 'context' THEN CASE WHEN source_id = ? THEN 'object_ids' ELSE 'referenced_by' END "
            "WHEN 'ontology_binding' THEN CASE WHEN source_id = ? THEN 'bindings' ELSE 'mapped_by' END "
            "WHEN 'relation_endpoint' THEN CASE WHEN source_id = ? THEN 'endpoints' ELSE 'relations' END "
            "ELSE CASE WHEN source_id = ? THEN 'endpoints' ELSE 'joins' END END AS via "
            "FROM links WHERE kind != 'relation' AND (source_id = ? OR target_id = ?) "
            "ORDER BY via, neighbor_id LIMIT ?",
            [object_id] * 8 + [limit],
        ).fetchall()
    objects = catalog.objects(row[0] for row in rows)
    return tuple(GraphNeighbor(via, summary(objects[identifier])) for identifier, via in rows if identifier in objects)
