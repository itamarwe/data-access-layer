"""Project native resources into searchable objects and explicit links."""

from dal.identity import stable_id
from .model import CompiledLink, CompilationRecords
from .records import compiled_object, containment_links, json_payload


def extract_records(document):
    resources = sorted(document["objects"], key=lambda item: item["id"])
    indexed = {item["id"]: item for item in resources}
    objects = tuple(compiled_object(item["id"], item["kind"], item["name"],
                                    item.get("parent_id"), item.get("source"), item)
                    for item in resources)
    links = list(containment_links(objects))
    def link(kind, left, right, owner, role=""):
        links.append(CompiledLink(stable_id("link", f"{kind}:{owner['id']}:{left}:{right}:{role}"),
                                  kind, left, right, json_payload(owner)))
    for item in resources:
        for target in item.get("bindings", []):
            link("ontology_binding", item["id"], target, item)
        for target in item.get("object_ids", []):
            link("context", item["id"], target, item)
        if item["kind"] == "join":
            for side in ("left", "right"):
                for position, endpoint in enumerate(item[side]):
                    link("join_column", item["id"], endpoint, item, f"{side}:{position}")
                    link("join_table", item["id"], indexed[endpoint]["parent_id"], item, side)
        elif item["kind"] == "relation":
            link("relation", item["from_id"], item["to_id"], item)
            for field in ("from_id", "to_id"):
                link("relation_endpoint", item["id"], item[field], item, field)
    unique = {item.link_id: item for item in links}
    return CompilationRecords(objects, tuple(unique[key] for key in sorted(unique)))
