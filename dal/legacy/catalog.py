"""Read an Legacy DuckDB graph into native, flat context objects."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import duckdb

from dal.evidence import EvidenceRecord
from dal.identity import stable_id

from .values import aliases, publication


@dataclass(frozen=True)
class ImportDiagnostic:
    code: str
    subject: str
    message: str


@dataclass(frozen=True)
class CatalogImport:
    document: dict[str, object]
    tables: int
    fields: int
    relationships: int
    diagnostics: tuple[ImportDiagnostic, ...]
    evidence: tuple[EvidenceRecord, ...] = ()
    omitted_records: tuple[dict, ...] = ()


class LegacyCatalogImporter:
    def __init__(self, database: Path):
        self.database = Path(database)

    def convert(self, model_name: str, evidence: Iterable[EvidenceRecord] = ()) -> CatalogImport:
        records = tuple(evidence)
        # Evidence resolves by subject_id; repeating every evidence ID in authored
        # objects would duplicate the snapshot and bloat search payloads.
        connection = duckdb.connect(str(self.database), read_only=True)
        try:
            columns = defaultdict(list)
            for row in _rows(connection, "node_columns"):
                columns[str(row["table_name"])].append(row)
            objects = []
            databases = set()
            families = set()
            table_count = 0
            for row in _rows(connection, "node_tables"):
                name = str(row["table_name"])
                database = name.rpartition(".")[0] or model_name
                databases.add(database)
                identifier = stable_id("table", name)
                table = {
                    "id": identifier, "kind": "table", "name": name, "source": name,
                    "parent_id": stable_id("database", database),
                    "status": publication(row.get("status")),
                }
                if row.get("grain"):
                    table["grain"] = {"description": str(row["grain"])}
                if row.get("description"):
                    table["description"] = str(row["description"])
                if row.get("aliases"):
                    table["aliases"] = aliases(row["aliases"])
                objects.append(table)
                table_count += 1
                for column in columns.get(name, ()):
                    field_name = str(column["column"])
                    field_id = stable_id("column", f"{name}.{field_name}")
                    field = {
                        "id": field_id, "kind": "column", "name": field_name,
                        "parent_id": identifier, "source": f"{name}.{field_name}",
                    }
                    if column.get("data_type"):
                        field["data_type"] = str(column["data_type"])
                    description = next((column.get(key) for key in (
                        "description_curated", "description", "description_schema",
                        "description_model", "description_generated", "description_derived",
                    ) if column.get(key)), None)
                    if description:
                        field["description"] = str(description)
                    if column.get("family"):
                        family = str(column["family"])
                        families.add(family)
                        field["_family"] = family
                    objects.append(field)
            objects.extend({"id": stable_id("database", name), "kind": "database", "name": name}
                           for name in sorted(databases))
            objects.extend({"id": stable_id("property", name), "kind": "property", "name": name,
                            "bindings": [item["id"] for item in objects if item.get("_family") == name]}
                           for name in sorted(families))
            for item in objects:
                item.pop("_family", None)
            joins, diagnostics = _joins(connection, objects)
            objects.extend(joins)
            omitted = tuple({"source_table": table, **row}
                            for table in ("proposals", "curated_join_specs", "assertions", "feedback_evidence")
                            for row in _rows(connection, table, required=False))
            for table in sorted({item["source_table"] for item in omitted}):
                count = sum(item["source_table"] == table for item in omitted)
                diagnostics.append(ImportDiagnostic(
                    "REVIEW_REQUIRED", table,
                    f"{count} source rows retained in import report; legacy subjects or review semantics require explicit mapping.",
                ))
        finally:
            connection.close()
        return CatalogImport(
            {"version": 1, "objects": objects}, table_count,
            sum(item["kind"] == "column" for item in objects), len(joins),
            tuple(diagnostics), records, omitted,
        )


def _joins(connection, objects):
    fields = {item["source"]: item for item in objects if item["kind"] == "column"}
    found = {}
    diagnostics = []
    candidates = [(str(row["col_a"]), str(row["col_b"]))
                  for row in _rows(connection, "edges_column", required=False)]
    candidates.extend((f"{row['table_a']}.{row['col_a']}", f"{row['table_b']}.{row['col_b']}")
                      for row in _rows(connection, "edges_join", required=False))
    missing = set()
    for left, right in candidates:
        natural_key = "|".join(sorted((left, right)))
        if left not in fields or right not in fields:
            if natural_key not in missing:
                diagnostics.append(ImportDiagnostic(
                    "MISSING_JOIN_ENDPOINT", natural_key,
                    "Relationship omitted because an endpoint is absent; its evidence remains in the snapshot.",
                ))
                missing.add(natural_key)
            continue
        identifier = stable_id("join", natural_key)
        found.setdefault(identifier, {
            "id": identifier, "kind": "join", "name": f"{left} ↔ {right}",
            "left": [fields[left]["id"]], "right": [fields[right]["id"]],
        })
        # edges_join confirms usage but omits the original expression. Casts,
        # composite predicates and filters cannot be reconstructed from IDs.
    return list(found.values()), diagnostics


def _rows(connection, table: str, *, required: bool = True) -> list[dict]:
    if not required and not connection.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = ?", [table],
    ).fetchone():
        return []
    cursor = connection.execute(f'SELECT * FROM "{table}"')
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, values)) for values in cursor.fetchall()]
