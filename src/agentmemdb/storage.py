"""SQLite storage: connections, schema and migrations."""

import os
import sqlite3

from agentmemdb.models import is_expired

SCHEMA_VERSION = 1
BUSY_TIMEOUT_SECONDS = 10

SCHEMA = """
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        content TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'other',
        tags TEXT DEFAULT '',
        importance TEXT NOT NULL DEFAULT 'normal',
        source TEXT DEFAULT '',
        thread_id TEXT DEFAULT '',
        expires_at TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS memory_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        content_snippet TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        previous_content TEXT DEFAULT '',
        FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS entities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_id INTEGER NOT NULL,
        entity_type TEXT NOT NULL,
        entity_value TEXT NOT NULL,
        FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_entities_type_value ON entities(entity_type, entity_value);
    CREATE INDEX IF NOT EXISTS idx_entities_memory ON entities(memory_id);
    CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
    CREATE INDEX IF NOT EXISTS idx_memories_thread ON memories(thread_id);
    CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance);
    CREATE INDEX IF NOT EXISTS idx_memory_history_memory ON memory_history(memory_id);

    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
    USING fts5(topic, content, tags, content=memories, content_rowid=id, tokenize='porter unicode61');

    -- Keep the FTS index in sync with memories
    CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
        INSERT INTO memories_fts(rowid, topic, content, tags)
        VALUES (new.id, new.topic, new.content, new.tags);
    END;
    CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
        INSERT INTO memories_fts(memories_fts, rowid, topic, content, tags)
        VALUES ('delete', old.id, old.topic, old.content, old.tags);
    END;
    CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
        INSERT INTO memories_fts(memories_fts, rowid, topic, content, tags)
        VALUES ('delete', old.id, old.topic, old.content, old.tags);
        INSERT INTO memories_fts(rowid, topic, content, tags)
        VALUES (new.id, new.topic, new.content, new.tags);
    END;
"""


class Store:
    """Connections to one database file; the schema is created or upgraded on first use."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._ready = False
        self._open: list[sqlite3.Connection] = []

    def connect(self) -> sqlite3.Connection:
        """Open a tracked connection; close it with release()."""
        if not self._ready:
            os.makedirs(os.path.dirname(self.path) or ".", mode=0o700, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=BUSY_TIMEOUT_SECONDS)
        self._open.append(db)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=NORMAL")
        db.create_function("is_expired", 1, is_expired)
        if not self._ready:
            migrate(db)
            self._ready = True
        return db

    @property
    def open_connections(self) -> int:
        return len(self._open)

    def release(self, keep: int = 0) -> None:
        """Roll back and close every connection opened after the first `keep`."""
        while len(self._open) > keep:
            db = self._open.pop()
            db.rollback()
            db.close()


def migrate(db: sqlite3.Connection) -> None:
    """Create the schema and upgrade databases written by older versions."""
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    if db.execute("PRAGMA user_version").fetchone()[0] >= SCHEMA_VERSION:
        return

    db.execute("BEGIN IMMEDIATE")
    if db.execute("PRAGMA user_version").fetchone()[0] < 1:
        _migrate_to_v1(db)
    db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    db.commit()


def _migrate_to_v1(db: sqlite3.Connection) -> None:
    """Porter stemming in FTS, previous_content in history, lowercased and deduplicated entities."""
    fts_sql = db.execute("SELECT sql FROM sqlite_master WHERE name = 'memories_fts'").fetchone()[0]
    if "porter" not in fts_sql:
        db.execute("DROP TABLE memories_fts")
        db.execute(
            "CREATE VIRTUAL TABLE memories_fts USING fts5(topic, content, tags, content=memories, "
            "content_rowid=id, tokenize='porter unicode61')"
        )
        db.execute("INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')")
    if "previous_content" not in {r["name"] for r in db.execute("PRAGMA table_info(memory_history)")}:
        db.execute("ALTER TABLE memory_history ADD COLUMN previous_content TEXT DEFAULT ''")
    db.execute("UPDATE entities SET entity_type = LOWER(TRIM(entity_type)), entity_value = LOWER(TRIM(entity_value))")
    db.execute(
        "DELETE FROM entities WHERE id NOT IN (SELECT MIN(id) FROM entities GROUP BY memory_id, entity_type, entity_value)"
    )
