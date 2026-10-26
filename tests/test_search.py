"""Pure helpers for query building and similarity."""

import pytest

from agentmemdb.search import filters, fts_queries, group_similar, is_similar, topic_words


def test_fts_queries_quote_terms_and_dedupe() -> None:
    assert fts_queries('PR #3056 "x"') == ['PR #3056 "x"', '"PR" "#3056" """x"""', '"PR" OR "#3056" OR """x"""']
    assert fts_queries("billing") == ["billing", '"billing"']
    assert fts_queries("--") == ["--"]


def test_topic_words_skip_stop_words_short_words_and_years() -> None:
    assert topic_words("The 2026 plan for billing-api and DB v12345") == {"plan", "billing", "api", "v12345"}


@pytest.mark.parametrize(
    ("a", "b", "similar"),
    [
        ("billing api retry policy", "billing api retry policy merged", True),
        ("billing api retry", "billing dashboard", False),
        ("postgres", "postgres", False),  # one shared word is not enough
    ],
)
def test_is_similar(a: str, b: str, similar: bool) -> None:
    assert is_similar(topic_words(a), topic_words(b)) is similar


def test_group_similar_respects_limit() -> None:
    memories = [
        {"id": 1, "topic": "billing api retry policy"},
        {"id": 2, "topic": "billing api retry policy merged"},
        {"id": 3, "topic": "website redesign astro"},
        {"id": 4, "topic": "website redesign astro launch"},
    ]
    groups = group_similar(memories, limit=10)
    assert [(g["memory"]["id"], [o["id"] for o in g["similar_to"]]) for g in groups] == [(1, [2]), (3, [4])]
    assert len(group_similar(memories, limit=1)) == 1


def test_filters() -> None:
    assert filters() == (" AND NOT is_expired(m.expires_at)", [])
    sql, params = filters("decision", "high", include_expired=True)
    assert sql == " AND m.category = ? AND m.importance IN (?,?)"
    assert params == ["decision", "high", "critical"]
