"""Relevance search (FTS5 + BM25 with a substring fallback) and duplicate detection."""

import re
import sqlite3
from typing import Any

from agentmemdb.models import IMPORTANCE_LEVELS, IMPORTANCE_RANK

Row = dict[str, Any]

STOP_WORDS = {"the", "and", "for", "with", "from", "that", "this", "are", "was", "has", "have", "not", "but"}

SEARCH_COLUMNS = (
    "m.id, m.topic, m.category, m.tags, m.importance, m.thread_id, m.expires_at, "
    "m.created_at, m.updated_at, LENGTH(m.content) AS content_length"
)

# BM25 weights for (topic, content, tags)
BM25_WEIGHTS = (10.0, 1.0, 5.0)


def filters(category: str = "", importance: str = "", include_expired: bool = False) -> tuple[str, list[Any]]:
    """SQL conditions on alias m for category, minimum importance and expiry."""
    sql, params = "", []
    if category:
        sql += " AND m.category = ?"
        params.append(category)
    if importance in IMPORTANCE_RANK:
        allowed = IMPORTANCE_LEVELS[IMPORTANCE_RANK[importance] :]
        sql += f" AND m.importance IN ({','.join('?' * len(allowed))})"
        params += allowed
    if not include_expired:
        sql += " AND NOT is_expired(m.expires_at)"
    return sql, params


def search(db: sqlite3.Connection, query: str, filter_sql: str, filter_params: list[Any], limit: int) -> list[Row]:
    """Try the query as typed, then all terms, then any term; fall back to substring matching."""
    for fts_query in fts_queries(query):
        results = _search_fts(db, fts_query, filter_sql, filter_params, limit)
        if results:
            return results
    return _search_substring(db, query, filter_sql, filter_params)[:limit]


def fts_phrase(term: str) -> str:
    return '"' + term.replace('"', '""') + '"'


def fts_queries(query: str) -> list[str]:
    """FTS5 queries in order: as typed, every term (AND), any term (OR)."""
    phrases = [fts_phrase(t) for t in query.split() if re.search(r"\w", t)]
    queries = [query]
    if phrases:
        queries += [" ".join(phrases), " OR ".join(phrases)]
    return list(dict.fromkeys(queries))


def _search_fts(
    db: sqlite3.Connection, fts_query: str, filter_sql: str, filter_params: list[Any], limit: int
) -> list[Row]:
    try:
        rows = db.execute(
            f"""SELECT {SEARCH_COLUMNS}, snippet(memories_fts, 1, '', '', '…', 32) AS snippet
                FROM memories_fts f
                JOIN memories m ON m.id = f.rowid
                WHERE memories_fts MATCH ?{filter_sql}
                ORDER BY bm25(memories_fts, {", ".join(map(str, BM25_WEIGHTS))}) LIMIT ?""",
            [fts_query, *filter_params, limit],
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(r) for r in rows]


def _search_substring(db: sqlite3.Connection, query: str, filter_sql: str, filter_params: list[Any]) -> list[Row]:
    """Partial words FTS can't match (e.g. "gres" in "postgres"), ranked by words matched."""
    words = [w.lower() for w in re.findall(r"\w+", query) if len(w) >= 2][:5]
    if not words:
        return []

    where = " OR ".join("(m.topic LIKE ? OR m.content LIKE ? OR m.tags LIKE ?)" for _ in words)
    rows = db.execute(
        f"SELECT {SEARCH_COLUMNS}, m.content FROM memories m WHERE ({where}){filter_sql}",
        [f"%{w}%" for w in words for _ in range(3)] + filter_params,
    ).fetchall()

    scored = []
    for row in rows:
        result = dict(row)
        content = result.pop("content")
        text = f"{result['topic']} {content} {result['tags']}".lower()
        result["snippet"] = content[:200] + ("…" if len(content) > 200 else "")
        scored.append((sum(w in text for w in words), result["updated_at"], result))
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    return [result for _, _, result in scored]


def topic_words(text: str) -> set[str]:
    """Significant words of a topic, ignoring stop words and short numbers like years."""
    return {
        w
        for w in re.findall(r"\w+", text.lower())
        if len(w) >= 3 and w not in STOP_WORDS and not (w.isdigit() and len(w) <= 4)
    }


def is_similar(words: set[str], other: set[str]) -> bool:
    """At least two shared words, covering 60% of the shorter topic."""
    shared = len(words & other)
    return shared >= 2 and shared / min(len(words), len(other)) >= 0.6


def find_similar(db: sqlite3.Connection, topic: str, limit: int = 3) -> list[Row]:
    """Memories whose topic matches exactly or shares most of its significant words."""
    duplicates = [
        dict(r, exact_match=True)
        for r in db.execute(
            "SELECT id, topic, category, importance, created_at FROM memories WHERE LOWER(topic) = LOWER(?)",
            (topic,),
        )
    ]
    words = topic_words(topic)
    if words:
        rows = db.execute(
            """SELECT m.id, m.topic, m.category, m.importance, m.created_at
               FROM memories_fts f
               JOIN memories m ON m.id = f.rowid
               WHERE memories_fts MATCH ?
               ORDER BY bm25(memories_fts) LIMIT 25""",
            ("topic : (" + " OR ".join(fts_phrase(w) for w in words) + ")",),
        ).fetchall()
        seen = {d["id"] for d in duplicates}
        duplicates += [dict(r) for r in rows if r["id"] not in seen and is_similar(words, topic_words(r["topic"]))]
    return duplicates[:limit]


def group_similar(memories: list[Row], limit: int) -> list[Row]:
    """Group memories (oldest first) whose topics share most of their significant words."""
    indexed = [(m, topic_words(m["topic"])) for m in memories]
    groups: list[Row] = []
    seen: set[int] = set()
    for i, (memory, words) in enumerate(indexed):
        if memory["id"] in seen or not words:
            continue
        similar = [
            other
            for other, other_words in indexed[i + 1 :]
            if other["id"] not in seen and other_words and is_similar(words, other_words)
        ]
        if similar:
            seen.update([memory["id"], *(o["id"] for o in similar)])
            groups.append({"memory": memory, "similar_to": similar})
            if len(groups) >= limit:
                break
    return groups
