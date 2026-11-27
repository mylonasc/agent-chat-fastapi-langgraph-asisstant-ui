"""Small transactional SQLite settings store, independent of chat persistence.

Only declarative, validated JSON is stored. No tool code or credentials.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class RevisionConflict(ValueError):
    pass


class SettingsStore:
    def __init__(self, path: str):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS tool_settings (scope TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL)"
            )

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def read(self, *scopes):
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT scope, revision, body FROM tool_settings WHERE scope IN ({','.join('?' for _ in scopes)})",
                scopes,
            ).fetchall()
        return {scope: (revision, json.loads(body)) for scope, revision, body in rows}

    def write(self, scope, revision, body, *, global_revision=None):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if global_revision is not None:
                row = connection.execute(
                    "SELECT revision FROM tool_settings WHERE scope='global'"
                ).fetchone()
                if (row[0] if row else 0) != global_revision:
                    raise RevisionConflict(
                        "Application tool settings changed. Refresh and try again."
                    )
            row = connection.execute(
                "SELECT revision FROM tool_settings WHERE scope=?", (scope,)
            ).fetchone()
            if (row[0] if row else 0) != revision:
                raise RevisionConflict("Tool settings changed. Refresh before saving.")
            connection.execute(
                "INSERT INTO tool_settings VALUES (?, ?, ?) ON CONFLICT(scope) DO UPDATE SET revision=excluded.revision, body=excluded.body",
                (scope, revision + 1, json.dumps(body)),
            )
        return revision + 1

    def delete_thread(self, thread_id):
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM tool_settings WHERE scope=?", (f"thread:{thread_id}",)
            )
