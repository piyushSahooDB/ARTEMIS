"""SQLite connection management for ARTEMIS."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union


def get_connection(db_path: Union[str, Path] = ":memory:") -> sqlite3.Connection:
    """Create and configure a SQLite connection.

    Enables WAL mode (for file databases), foreign keys, and dictionary-like row factory.
    """
    is_memory = str(db_path) == ":memory:" or str(db_path).startswith("file::memory:")

    if not is_memory:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(db_path),
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row

    # Enforce foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON;")

    # Enable write-ahead logging and normal synchronization for file-based DBs
    if not is_memory:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")

    return conn
