"""Shared fixtures. The environment is pinned to a temp config and database before agentmemdb is imported."""

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

TEST_HOME = tempfile.mkdtemp(prefix="agentmemdb-tests-")
TEST_CONFIG = {"auto_tags": {"datadog": "datadog", "github": "github"}, "instructions": "Test policy: always save."}

os.environ["AGENTMEMDB_CONFIG"] = os.path.join(TEST_HOME, "config.json")
os.environ["AGENTMEMDB_DB_PATH"] = os.path.join(TEST_HOME, "default.db")
with open(os.environ["AGENTMEMDB_CONFIG"], "w", encoding="utf-8") as f:
    json.dump(TEST_CONFIG, f)

from agentmemdb import server  # noqa: E402
from agentmemdb.storage import Store  # noqa: E402
from tests.helpers import Call  # noqa: E402


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Store:
    """A fresh, empty database for each test."""
    fresh = Store(str(tmp_path / "memory.db"))
    monkeypatch.setattr(server, "store", fresh)
    return fresh


@pytest.fixture
def call(store: Store) -> Call:
    """Call a tool function and decode its JSON response."""

    def _call(fn: Callable[..., str], **kwargs: Any) -> dict[str, Any]:
        result: dict[str, Any] = json.loads(fn(**kwargs))
        return result

    return _call


@pytest.fixture
def seeded(call: Call) -> Call:
    """A database with a few representative memories, including one expired."""
    call(
        server.save_memory,
        topic="billing-api PR 3056 retry policy changes",
        content="Updated Datadog monitors for the payment retries.",
        category="project",
        entities='[{"type":"repo","value":"Billing-API"}]',
    )
    call(
        server.save_memory,
        topic="OPS-2406 GitHub secret scanning access",
        content="Granted access to the security team.",
        category="decision",
    )
    call(
        server.save_memory,
        topic="example.com website redesign",
        content="Moved the site to Astro.",
        category="project",
        importance="low",
    )
    call(server.save_memory, topic="Old expired note", content="Datadog trial ends.", expires_at="2020-01-01")
    return call
