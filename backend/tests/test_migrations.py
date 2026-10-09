import os
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import patch

import migrate


def test_migrations_are_repeatable():
    database = Path(__file__).parent / f".migration-{uuid.uuid4().hex}.sqlite"
    url = f"sqlite:///{database.as_posix()}"
    try:
        with patch.dict(os.environ, {"DATABASE_URL": url}):
            migrate.migrate()
            migrate.migrate()

        connection = sqlite3.connect(database)
        try:
            versions = connection.execute("SELECT version FROM schema_migrations").fetchall()
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            connection.close()

        assert versions == [("0001_initial",), ("0002_document_files",)]
        assert {"documents", "reports", "document_files"} <= tables
    finally:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{database}{suffix}").unlink(missing_ok=True)
