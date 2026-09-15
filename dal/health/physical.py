"""Compare native tables with explicit, read-only physical snapshots."""

from collections.abc import Mapping
from datetime import datetime, timedelta

from .model import HealthIssue

REFRESH_COMMAND = "dal build --help"


def inspect_physical(documents, catalog, now: datetime, maximum_age: timedelta):
    failures, gaps = [], []
    resources = [item for authored in documents for item in authored.value["objects"] if isinstance(item, Mapping)]
    columns = {}
    for item in resources:
        if item.get("kind") == "column":
            columns.setdefault(item.get("parent_id"), []).append(item)
    for resource in resources:
        if resource.get("kind") != "table" or resource.get("status") == "deprecated":
            continue
        source, location = resource.get("source"), str(resource.get("id"))
        if not source:
            gaps.append(HealthIssue("SOURCE_MISSING", location, "No physical source is defined; existence cannot be checked.", "dal proposal create --help"))
            continue
        try:
            table = catalog.table(source)
            if table is None:
                failures.append(HealthIssue("SOURCE_TABLE_MISSING", location, f"Source {source!r} is absent from the supplied snapshot.", REFRESH_COMMAND))
                continue
            updated = table.data_updated_at
            if updated is None:
                gaps.append(HealthIssue("DATA_FRESHNESS_NOT_CHECKED", location, "The snapshot has no data update time; schema collection time is not data freshness.", REFRESH_COMMAND))
            elif updated.tzinfo is None or updated.utcoffset() is None:
                failures.append(HealthIssue("CATALOG_SNAPSHOT_CORRUPT", location, "Data timestamp must include a timezone.", REFRESH_COMMAND))
            elif now - updated > maximum_age:
                failures.append(HealthIssue("SOURCE_DATA_STALE", location, f"Source {source!r} exceeds the configured data age.", "Refresh the upstream source data, then collect a new physical snapshot."))
            expected = {item["name"]: item.get("data_type") for item in columns.get(resource["id"], []) if not item.get("expression") or item["expression"] == item["name"]}
            for name, data_type in expected.items():
                actual = table.columns.get(name)
                if actual is None or (data_type and str(actual).casefold() != str(data_type).casefold()):
                    failures.append(HealthIssue("SOURCE_SCHEMA_DRIFT", f"{location}/{name}", f"Column {name!r}: expected {data_type!r}, snapshot contains {actual!r}.", REFRESH_COMMAND))
            for name in sorted(set(table.columns) - set(expected)):
                gaps.append(HealthIssue("SOURCE_COLUMN_NOT_MODELED", f"{location}/{name}", f"Column {name!r} is not represented in the graph.", REFRESH_COMMAND))
        except Exception as error:
            failures.append(HealthIssue("CATALOG_SNAPSHOT_CORRUPT", location, f"Cannot read snapshot: {error}", REFRESH_COMMAND))
    return failures, gaps
