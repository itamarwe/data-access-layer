"""Short-lived reads of immutable query bundles."""

from contextlib import contextmanager
from pathlib import Path
from threading import RLock

import duckdb


_read_lock = RLock()


@contextmanager
def read_only_connection(path: Path):
    # Concurrent attachment/closure of the same file can race in DuckDB.
    # Hold the lock for the connection lifetime, including health-check reads.
    with _read_lock:
        with duckdb.connect(str(path), read_only=True) as connection:
            yield connection
