"""Read-only streaming extraction from an Legacy context graph."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from datetime import datetime
from pathlib import Path

import duckdb

from .legacy_common import LegacyRecordFactory
from .legacy_edges import column_edge_records, join_edge_records
from .legacy_nodes import column_records, table_records, corrupt_table_records
from .model import EvidenceRecord

RowConverter = Callable[
    [Mapping[str, object], LegacyRecordFactory], Iterable[EvidenceRecord]
]

TABLE_CONVERTERS: tuple[tuple[str, RowConverter], ...] = (
    ("node_tables", table_records),
    ("node_columns", column_records),
    ("edges_column", column_edge_records),
    ("edges_join", join_edge_records),
    ("corrupt_tables", corrupt_table_records),
)


class LegacyEvidenceExtractor:
    """Stream normalized evidence without modifying or attaching the source DB."""

    def __init__(
        self,
        database: Path,
        source_revision: str,
        collected_at: datetime,
        batch_size: int = 2_048,
    ):
        self.database = database
        self.factory = LegacyRecordFactory(source_revision, collected_at)
        self.batch_size = batch_size

    def records(self) -> Iterator[EvidenceRecord]:
        connection = duckdb.connect(str(self.database), read_only=True)
        seen: set[str] = set()
        try:
            available = _table_names(connection)
            for table, converter in TABLE_CONVERTERS:
                if table in available:
                    for record in self._table_records(connection, table, converter):
                        if record.record_id not in seen:
                            seen.add(record.record_id)
                            yield record
        finally:
            connection.close()

    def _table_records(
        self,
        connection: duckdb.DuckDBPyConnection,
        table: str,
        converter: RowConverter,
    ) -> Iterator[EvidenceRecord]:
        cursor = connection.execute(f'SELECT * FROM "{table}"')
        columns = tuple(item[0] for item in cursor.description)
        while rows := cursor.fetchmany(self.batch_size):
            for values in rows:
                row = dict(zip(columns, values))
                yield from converter(row, self.factory)


def _table_names(connection: duckdb.DuckDBPyConnection) -> set[str]:
    rows = connection.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main'"
    ).fetchall()
    return {row[0] for row in rows}
