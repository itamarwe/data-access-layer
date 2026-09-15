"""Glue metadata collection; no queries are submitted and no warehouse data is read."""

from datetime import datetime

from dal.evidence import SourceKind, content_digest
from dal.identity import stable_id

from .types import CollectionResult, claim


def collect_glue(client, database_names, *, collected_at: datetime, max_tables: int = 10000) -> CollectionResult:
    if max_tables < 1:
        raise ValueError("max_tables must be positive")
    objects, evidence = [], []
    count = 0
    for database in database_names:
        objects.append({"id": stable_id("database", database), "kind": "database", "name": database})
        for page in client.get_paginator("get_tables").paginate(DatabaseName=database):
            for table in page.get("TableList", []):
                count += 1
                if count > max_tables:
                    raise ValueError("Glue table limit exceeded; narrow the selected databases")
                result = glue_table(database, table, collected_at=collected_at)
                objects.extend(result.objects)
                evidence.extend(result.evidence)
    return CollectionResult(tuple(objects), tuple(evidence))


def glue_table(database, table, *, collected_at):
    source = f"{database}.{table['Name']}"
    identifier = stable_id("table", source)
    descriptor = table.get("StorageDescriptor") or {}
    columns = [*descriptor.get("Columns", []), *table.get("PartitionKeys", [])]
    revision = content_digest({
        "name": source, "columns": columns, "parameters": table.get("Parameters", {}),
        "updated_at": str(table.get("UpdateTime", "")),
    })
    objects = [{"id": identifier, "kind": "table", "name": source, "source": source,
                "parent_id": stable_id("database", database)}]
    evidence = []
    def add(subject, path, value):
        evidence.append(claim(subject, path, value, kind=SourceKind.DATABASE_SCHEMA,
                              revision=revision, collected_at=collected_at, uri=f"glue:{source}#{path}"))
    add(identifier, "/exists", True)
    add(identifier, "/schema", [{"name": col["Name"], "type": col.get("Type")} for col in columns])
    comment = (table.get("Parameters") or {}).get("comment") or table.get("Description")
    if comment:
        add(identifier, "/description", comment)
        objects[0]["description"] = comment
    seen = set()
    for col in columns:
        name = col["Name"]
        if name in seen:
            continue
        seen.add(name)
        column_id = stable_id("column", f"{source}.{name}")
        item = {"id": column_id, "kind": "column", "name": name,
                "parent_id": identifier, "source": f"{source}.{name}"}
        if col.get("Type"):
            item["data_type"] = col["Type"]
            add(column_id, "/data_type", col["Type"])
        if col.get("Comment"):
            item["description"] = col["Comment"]
            add(column_id, "/description", col["Comment"])
        add(column_id, "/exists", True)
        objects.append(item)
    return CollectionResult(tuple(objects), tuple(evidence))
