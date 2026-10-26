"""Helpers shared by the test modules."""

import sqlite3
from collections.abc import Callable
from typing import Any

Call = Callable[..., dict[str, Any]]


def other_writer_can_lock(path: str) -> bool:
    """True when another connection can take the database write lock."""
    db = sqlite3.connect(path, timeout=1, isolation_level=None)
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("ROLLBACK")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        db.close()
