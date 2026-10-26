"""Behaviour of the MCP tools against a fresh database."""

import asyncio

import pytest

from agentmemdb import server
from agentmemdb.storage import Store
from tests.helpers import Call


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("billing-api", "billing-api PR 3056"),
        ("OPS-2406", "OPS-2406"),
        ("PR #3056", "billing-api PR 3056"),
        ("example.com", "example.com"),
        ("monitor", "billing-api PR 3056"),  # stemmed: monitors
        ("xampl", "example.com"),  # substring fallback
        ("tags:datadog", "billing-api PR 3056"),  # raw FTS5 syntax
    ],
)
def test_search_handles_punctuation_stemming_and_fallback(seeded: Call, query: str, expected: str) -> None:
    res = seeded(server.search_memory, query=query)
    assert res["count"] >= 1
    assert res["results"][0]["topic"].startswith(expected)


def test_search_returns_snippets_and_honours_filters(seeded: Call) -> None:
    res = seeded(server.search_memory, query="datadog")
    assert all("snippet" in r and "content" not in r for r in res["results"])
    assert all(r["topic"] != "Old expired note" for r in res["results"])

    with_expired = seeded(server.search_memory, query="datadog", include_expired=True)
    assert any(r["topic"] == "Old expired note" for r in with_expired["results"])

    full = seeded(server.search_memory, query="OPS-2406", full_content=True)["results"][0]
    assert full["content"] == "Granted access to the security team."
    assert "snippet" not in full

    assert seeded(server.search_memory, query="website", importance="normal")["count"] == 0
    assert seeded(server.search_memory, query="website", importance="low")["count"] == 1


def test_save_adds_auto_tags_and_source(call: Call) -> None:
    res = call(server.save_memory, topic="Alerting", content="Moved alerts to Datadog", tags="alerts", source="cli")
    assert res["tags"] == "alerts,datadog"
    assert res["auto_tags_added"] == ["datadog"]
    assert call(server.get_memory, memory_id=res["id"])["source"] == "cli"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"category": "nope"},
        {"importance": "urgent"},
        {"expires_at": "next week"},
        {"entities": '["billing-api"]'},
        {"entities": '{"type":"x"}'},
        {"entities": '[{"type":"service"}]'},
        {"entities": "not json"},
    ],
)
def test_save_rejects_invalid_input_without_writing(call: Call, kwargs: dict[str, str]) -> None:
    assert "error" in call(server.save_memory, topic="t", content="c", **kwargs)
    assert call(server.get_stats)["total_memories"] == 0


def test_duplicate_detection_is_specific(seeded: Call) -> None:
    res = seeded(server.save_memory, topic="billing-api PR 3056 retry policy changes merged", content="Merged.")
    assert [d["topic"] for d in res["possible_duplicates"]] == ["billing-api PR 3056 retry policy changes"]

    res = seeded(server.save_memory, topic="Memory MCP database locked fix", content="Unrelated to github.")
    assert "possible_duplicates" not in res

    assert seeded(server.find_duplicates, limit=1)["group_count"] == 1
    similar = seeded(server.find_duplicates, topic="billing-api retry policy")
    assert similar["count"] == 2


def test_entities_are_normalized(seeded: Call) -> None:
    assert seeded(server.find_by_entity, entity_type="REPO", entity_value="billing-api")["count"] == 1
    assert [e["entity_value"] for e in seeded(server.list_entities)["results"]] == ["billing-api"]
    assert seeded(server.list_entities, entity_type="person")["count"] == 0


def test_update_keeps_previous_content(call: Call) -> None:
    mid = call(server.save_memory, topic="Update target", content="original text")["id"]
    assert call(server.update_memory, memory_id=mid)["status"] == "unchanged"

    res = call(server.update_memory, memory_id=mid, content="new text", thread_id="t1")
    assert res["changed"] == ["content", "thread_id"]
    history = call(server.get_memory_history, memory_id=mid)["history"]
    assert history[-1]["previous_content"] == "original text"
    assert "previous_content" not in history[0]

    assert "error" in call(server.update_memory, memory_id=mid, expires_at="soon")
    assert "error" in call(server.update_memory, memory_id=mid, category="nope")


def test_append_reports_only_new_tags(call: Call) -> None:
    mid = call(server.save_memory, topic="Append target", content="about datadog")["id"]
    assert call(server.append_memory, memory_id=mid, content="more datadog", source="omp")["new_tags"] is None

    res = call(server.append_memory, memory_id=mid, content="now github too")
    assert res["new_tags"] == ["github"]
    assert res["total_appends"] == 2
    assert "*(from omp)*" in call(server.get_memory, memory_id=mid)["content"]


def test_missing_memory_returns_error(call: Call) -> None:
    for fn in (server.get_memory, server.get_memory_history, server.delete_memory):
        assert call(fn, memory_id=999) == {"error": "Memory with id 999 not found"}
    assert "error" in call(server.append_memory, memory_id=999, content="x")
    assert "error" in call(server.update_memory, memory_id=999, topic="x")


def test_delete_removes_memory_and_entities(seeded: Call) -> None:
    mid = seeded(server.search_memory, query="billing-api")["results"][0]["id"]
    assert seeded(server.delete_memory, memory_id=mid)["status"] == "deleted"
    assert seeded(server.find_by_entity, entity_value="billing-api")["count"] == 0
    assert seeded(server.list_entities)["count"] == 0


def test_threads_and_listing(call: Call) -> None:
    call(server.save_memory, topic="Step one", content="a", thread_id="rollout", tags="infra")
    call(server.save_memory, topic="Step two", content="b", thread_id="rollout", category="decision")
    call(server.save_memory, topic="Elsewhere", content="c")

    thread = call(server.get_thread, thread_id="rollout")
    assert [m["topic"] for m in thread["results"]] == ["Step one", "Step two"]
    assert call(server.list_threads)["threads"][0]["memory_count"] == 2
    assert call(server.list_memories, tag="infra")["count"] == 1
    assert call(server.list_memories, category="decision")["count"] == 1
    assert call(server.list_memories, thread_id="rollout", limit=1)["count"] == 1


def test_cleanup_expired_dry_run_then_delete(seeded: Call) -> None:
    dry = seeded(server.cleanup_expired)
    assert dry["status"] == "dry_run"
    assert [m["topic"] for m in dry["expired"]] == ["Old expired note"]
    assert seeded(server.cleanup_expired, dry_run=False)["deleted_count"] == 1
    assert seeded(server.cleanup_expired)["status"] == "clean"


def test_daily_summary_and_stats(seeded: Call, store: Store) -> None:
    assert seeded(server.get_daily_summary)["total"] == 4
    assert "error" in seeded(server.get_daily_summary, date="25-10-2026")

    stats = seeded(server.get_stats)
    assert stats["total_memories"] == 4
    assert stats["expired_memories"] == 1
    assert stats["db_path"] == store.path


def test_non_ascii_is_not_escaped(call: Call) -> None:
    out = server.save_memory(topic="決済テスト", content="コンビニ決済")
    assert "決済テスト" in out
    assert call(server.search_memory, query="コンビニ")["count"] == 1


def test_tool_schemas() -> None:
    tools = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
    assert len(tools) == 16
    assert "full_content" in tools["search_memory"].inputSchema["properties"]
    assert tools["save_memory"].description
    assert tools["save_memory"].description.startswith("Save a piece")
