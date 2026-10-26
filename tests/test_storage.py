"""Connection lifecycle, locking and schema migration."""

import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

import pytest

from agentmemdb import server
from agentmemdb.storage import SCHEMA, SCHEMA_VERSION, Store
from tests.helpers import Call, other_writer_can_lock


def test_rejected_input_leaves_no_lock_or_open_connection(call: Call, store: Store) -> None:
    call(server.get_stats)
    assert "error" in call(server.save_memory, topic="t", content="c", entities='["billing-api"]')
    assert other_writer_can_lock(store.path)
    assert store.open_connections == 0


def test_exception_mid_write_releases_lock(store: Store) -> None:
    @server.managed
    def boom() -> str:
        server.store.connect().execute(
            "INSERT INTO memories (topic, content, created_at, updated_at) VALUES ('x', 'y', 'now', 'now')"
        )
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        boom()
    assert other_writer_can_lock(store.path)
    assert store.open_connections == 0
    with closing(sqlite3.connect(store.path)) as db:
        assert db.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 0


def test_new_database_directory_is_private(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "data" / "memory.db"))
    store.connect()
    store.release()
    assert stat.S_IMODE(os.stat(tmp_path / "data").st_mode) == 0o700


def test_migration_from_v0_schema(tmp_path: Path, call: Call, monkeypatch: pytest.MonkeyPatch) -> None:
    path = str(tmp_path / "legacy.db")
    with closing(sqlite3.connect(path)) as legacy:
        legacy.executescript(
            SCHEMA.replace(", tokenize='porter unicode61'", "").replace("previous_content TEXT DEFAULT '',", "")
        )
        legacy.execute(
            "INSERT INTO memories (topic, content, created_at, updated_at) VALUES ('Datadog monitors', 'c', 'now', 'now')"
        )
        legacy.executemany(
            "INSERT INTO entities (memory_id, entity_type, entity_value) VALUES (1, ?, ?)",
            [("Org", "ACME"), ("org", "acme")],
        )
        legacy.commit()

    monkeypatch.setattr(server, "store", Store(path))
    assert call(server.search_memory, query="monitor")["count"] == 1

    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert db.execute("SELECT entity_type, entity_value FROM entities").fetchall() == [("org", "acme")]
        assert "previous_content" in [r[1] for r in db.execute("PRAGMA table_info(memory_history)")]
        db.execute("INSERT INTO memories_fts(memories_fts) VALUES ('integrity-check')")
