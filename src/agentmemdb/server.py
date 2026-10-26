"""The MCP server: memory tools over one SQLite database shared by every connected agent."""

import base64
import functools
import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone
from importlib.resources import files
from typing import Any, ParamSpec

from mcp.server.fastmcp import FastMCP
from mcp.types import Icon

from agentmemdb import __version__
from agentmemdb.config import load_settings
from agentmemdb.models import (
    ToolError,
    check_category,
    check_expiry,
    check_importance,
    clamp,
    is_expired,
    parse_entities,
    parse_tags,
    utc_now,
)
from agentmemdb.search import filters, find_similar, group_similar, search
from agentmemdb.storage import Store

PROJECT_URL = "https://github.com/harsh-gulhane/agentmemdb"

P = ParamSpec("P")


def _icon() -> Icon:
    svg = files("agentmemdb").joinpath("icon.svg").read_bytes()
    return Icon(src="data:image/svg+xml;base64," + base64.b64encode(svg).decode(), mimeType="image/svg+xml")


settings = load_settings()
store = Store(settings.db_path)

mcp = FastMCP(
    name="agentmemdb",
    instructions=settings.instructions,
    website_url=PROJECT_URL,
    icons=[_icon()],
    log_level="WARNING",
)
# FastMCP has no version argument; report ours in serverInfo instead of the mcp SDK's
mcp._mcp_server.version = __version__


def managed(fn: Callable[P, str]) -> Callable[P, str]:
    """Return ToolError as {"error": ...} and always roll back and close the call's connections."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> str:
        current = store
        mark = current.open_connections
        try:
            return fn(*args, **kwargs)
        except ToolError as err:
            return _json({"error": str(err)})
        finally:
            current.release(mark)

    return wrapper


def tool(fn: Callable[P, str]) -> Callable[P, str]:
    """Register fn as an MCP tool."""
    wrapped = managed(fn)
    mcp.tool()(wrapped)
    return wrapped


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _client_name() -> str:
    """Name the connected MCP client reports (e.g. "claude-code"); empty outside a request."""
    try:
        params = mcp.get_context().session.client_params
    except ValueError:
        return ""
    return params.clientInfo.name if params else ""


def _get_memory_row(db: sqlite3.Connection, memory_id: int, columns: str = "*") -> sqlite3.Row:
    row: sqlite3.Row | None = db.execute(f"SELECT {columns} FROM memories WHERE id = ?", (memory_id,)).fetchone()
    if not row:
        raise ToolError(f"Memory with id {memory_id} not found")
    return row


def _rows(db: sqlite3.Connection, sql: str, params: Any = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in db.execute(sql, params)]


# ─── Core memory tools ───────────────────────────────────────────────


@tool
def save_memory(
    topic: str,
    content: str,
    category: str = "other",
    tags: str = "",
    importance: str = "normal",
    source: str = "",
    thread_id: str = "",
    entities: str = "",
    expires_at: str = "",
) -> str:
    """Save a piece of context/memory for future conversations.
    Warns about likely duplicates (consider append_memory instead) and adds configured auto-tags.

    Args:
        topic: Short title (e.g. "billing-api Postgres migration decision", "AAPL stock analysis")
        content: Detailed context to remember — include conclusions, data, links, action items
        category: One of: conversation, decision, incident, research, person, project, howto, config, other
        tags: Comma-separated tags (e.g. "postgres,database,billing")
        importance: One of: low, normal, high, critical
        source: Where this came from (default: the connected client's name, e.g. "claude-code")
        thread_id: Link related memories together with the same thread ID (e.g. "incident-2026-03-24")
        entities: JSON array of objects, e.g. [{"type":"service","value":"billing-api"},{"type":"person","value":"alice"}]
        expires_at: Optional expiry date (YYYY-MM-DD) after which this memory is less relevant
    """
    check_category(category)
    check_importance(importance)
    if expires_at:
        check_expiry(expires_at)
    entity_list = parse_entities(entities)
    source = source or _client_name()

    db = store.connect()
    duplicates = find_similar(db, topic)
    auto_tags = settings.tags_for(topic, content)
    tags_str = ",".join(dict.fromkeys(parse_tags(tags) + auto_tags))

    now = utc_now().isoformat()
    cursor = db.execute(
        """INSERT INTO memories
           (topic, content, category, tags, importance, source, thread_id, expires_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (topic, content, category, tags_str, importance, source, thread_id, expires_at, now, now),
    )
    memory_id = cursor.lastrowid
    db.executemany(
        "INSERT INTO entities (memory_id, entity_type, entity_value) VALUES (?, ?, ?)",
        [(memory_id, t, v) for t, v in entity_list],
    )
    db.execute(
        "INSERT INTO memory_history (memory_id, action, content_snippet, created_at) VALUES (?, ?, ?, ?)",
        (memory_id, "created", content[:100], now),
    )
    db.commit()

    result: dict[str, Any] = {
        "status": "saved",
        "id": memory_id,
        "topic": topic,
        "category": category,
        "tags": tags_str,
    }
    if auto_tags:
        result["auto_tags_added"] = auto_tags
    if duplicates:
        result["possible_duplicates"] = [
            {"id": d["id"], "topic": d["topic"], "exact_match": d.get("exact_match", False)} for d in duplicates
        ]
    return _json(result)


@tool
def append_memory(memory_id: int, content: str, source: str = "") -> str:
    """Append additional context to an existing memory without replacing it.
    The new content is added with a timestamp separator. History is tracked.

    Args:
        memory_id: The ID of the memory to append to
        content: New content to add (will be appended with a timestamp)
        source: Where this update came from (default: the connected client's name)
    """
    source = source or _client_name()
    db = store.connect()
    row = _get_memory_row(db, memory_id)

    now = utc_now()
    separator = f"\n\n---\n**[Update {now.strftime('%Y-%m-%d %H:%M UTC')}]**"
    if source:
        separator += f" *(from {source})*"
    separator += "\n"

    existing_tags = parse_tags(row["tags"] or "")
    new_tags = [t for t in settings.tags_for(content) if t not in existing_tags]

    db.execute(
        "UPDATE memories SET content = ?, tags = ?, updated_at = ? WHERE id = ?",
        (row["content"] + separator + content, ",".join(existing_tags + new_tags), now.isoformat(), memory_id),
    )
    db.execute(
        "INSERT INTO memory_history (memory_id, action, content_snippet, created_at) VALUES (?, ?, ?, ?)",
        (memory_id, "appended", content[:100], now.isoformat()),
    )
    db.commit()

    append_count = db.execute(
        "SELECT COUNT(*) FROM memory_history WHERE memory_id = ? AND action = 'appended'", (memory_id,)
    ).fetchone()[0]
    return _json(
        {
            "status": "appended",
            "id": memory_id,
            "topic": row["topic"],
            "total_appends": append_count,
            "new_tags": new_tags or None,
        }
    )


@tool
def search_memory(
    query: str,
    category: str = "",
    importance: str = "",
    limit: int = 10,
    include_expired: bool = False,
    full_content: bool = False,
) -> str:
    """Search memories by relevance: full-text search with stemming (topic and tag matches rank highest),
    falling back to substring matching. Returns a snippet per memory; use get_memory for the full text.
    Expired memories are excluded by default.

    Args:
        query: Search query — plain words, hyphenated names, IDs, or FTS5 syntax (e.g. "tags:aws", "datadog OR sentry")
        category: Filter by category (optional)
        importance: Filter by minimum importance: low, normal, high, critical (optional)
        limit: Maximum number of results (default: 10, max: 100)
        include_expired: Set to true to include expired memories (default: false)
        full_content: Set to true to return full content instead of snippets (default: false)
    """
    db = store.connect()
    filter_sql, filter_params = filters(category, importance, include_expired)
    results = search(db, query, filter_sql, filter_params, clamp(limit))

    if full_content and results:
        ids = [r["id"] for r in results]
        placeholders = ",".join("?" * len(ids))
        contents = dict(db.execute(f"SELECT id, content FROM memories WHERE id IN ({placeholders})", ids).fetchall())
        for r in results:
            r.pop("snippet", None)
            r["content"] = contents[r["id"]]

    return _json({"count": len(results), "results": results})


@tool
def list_memories(
    category: str = "", tag: str = "", thread_id: str = "", limit: int = 25, include_expired: bool = False
) -> str:
    """List saved memories with optional filters. Expired memories excluded by default.

    Args:
        category: Filter by category (optional)
        tag: Filter by tag (optional)
        thread_id: Filter by thread ID to see all related memories (optional)
        limit: Maximum number of results (default: 25, max: 200)
        include_expired: Set to true to include expired memories (default: false)
    """
    db = store.connect()
    filter_sql, params = filters(category, include_expired=include_expired)
    sql = (
        "SELECT m.id, m.topic, m.category, m.tags, m.importance, m.thread_id, m.expires_at, m.created_at, "
        f"m.updated_at FROM memories m WHERE 1=1{filter_sql}"
    )
    if tag:
        sql += " AND ',' || m.tags || ',' LIKE ?"
        params.append(f"%,{tag.strip()},%")
    if thread_id:
        sql += " AND m.thread_id = ?"
        params.append(thread_id)
    sql += " ORDER BY m.updated_at DESC LIMIT ?"
    params.append(clamp(limit, 200))

    results = _rows(db, sql, params)
    return _json({"count": len(results), "results": results})


@tool
def get_memory(memory_id: int) -> str:
    """Get the full content of a specific memory including linked entities and edit history.

    Args:
        memory_id: The ID of the memory to retrieve
    """
    db = store.connect()
    result = dict(_get_memory_row(db, memory_id))
    result["is_expired"] = is_expired(result.get("expires_at", ""))
    result["entities"] = _rows(db, "SELECT entity_type, entity_value FROM entities WHERE memory_id = ?", (memory_id,))
    result["history"] = _rows(
        db,
        "SELECT action, content_snippet, created_at FROM memory_history WHERE memory_id = ? ORDER BY created_at",
        (memory_id,),
    )
    return _json(result)


@tool
def update_memory(
    memory_id: int,
    topic: str = "",
    content: str = "",
    category: str = "",
    tags: str = "",
    importance: str = "",
    thread_id: str = "",
    expires_at: str = "",
) -> str:
    """Update an existing memory. Only provided fields are updated. Use append_memory to add context without replacing.
    Replaced content is kept in the memory's history (see get_memory_history).

    Args:
        memory_id: The ID of the memory to update
        topic: New topic (leave empty to keep existing)
        content: New content (leave empty to keep existing)
        category: New category (leave empty to keep existing)
        tags: New tags (leave empty to keep existing)
        importance: New importance (leave empty to keep existing)
        thread_id: New thread ID (leave empty to keep existing)
        expires_at: New expiry (leave empty to keep existing)
    """
    if category:
        check_category(category)
    if importance:
        check_importance(importance)
    if expires_at:
        check_expiry(expires_at)

    db = store.connect()
    row = _get_memory_row(db, memory_id)
    fields = {
        "topic": topic,
        "content": content,
        "category": category,
        "tags": tags,
        "importance": importance,
        "thread_id": thread_id,
        "expires_at": expires_at,
    }
    updates = {k: v or row[k] for k, v in fields.items()}
    changed = [k for k in fields if updates[k] != row[k]]
    if not changed:
        return _json({"status": "unchanged", "id": memory_id, "topic": row["topic"]})

    now = utc_now().isoformat()
    db.execute(
        """UPDATE memories SET topic=?, content=?, category=?, tags=?, importance=?,
           thread_id=?, expires_at=?, updated_at=? WHERE id=?""",
        (*updates.values(), now, memory_id),
    )
    db.execute(
        """INSERT INTO memory_history (memory_id, action, content_snippet, created_at, previous_content)
           VALUES (?, ?, ?, ?, ?)""",
        (memory_id, "updated", f"fields: {','.join(changed)}", now, row["content"] if "content" in changed else ""),
    )
    db.commit()
    return _json({"status": "updated", "id": memory_id, "topic": updates["topic"], "changed": changed})


@tool
def delete_memory(memory_id: int) -> str:
    """Delete a memory and its linked entities.

    Args:
        memory_id: The ID of the memory to delete
    """
    db = store.connect()
    row = _get_memory_row(db, memory_id, "topic")
    db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    db.commit()
    return _json({"status": "deleted", "id": memory_id, "topic": row["topic"]})


# ─── Entity tools ────────────────────────────────────────────────────


@tool
def find_by_entity(entity_type: str = "", entity_value: str = "", limit: int = 25) -> str:
    """Find all memories linked to a specific entity (person, service, account, etc.).

    Args:
        entity_type: Type of entity (e.g. "person", "service", "account", "bucket", "ticket")
        entity_value: Value to search, substring match (e.g. "alice", "billing-api", "prod-db")
        limit: Maximum results (default: 25, max: 200)
    """
    db = store.connect()
    filter_sql, params = filters()
    sql = f"""
        SELECT DISTINCT m.id, m.topic, m.category, m.tags, m.importance, m.thread_id, m.expires_at, m.created_at
        FROM memories m
        JOIN entities e ON e.memory_id = m.id
        WHERE 1=1{filter_sql}
    """
    if entity_type:
        sql += " AND e.entity_type = ?"
        params.append(entity_type.strip().lower())
    if entity_value:
        sql += " AND e.entity_value LIKE ?"
        params.append(f"%{entity_value.strip().lower()}%")
    sql += " ORDER BY m.updated_at DESC LIMIT ?"
    params.append(clamp(limit, 200))

    results = _rows(db, sql, params)
    return _json({"count": len(results), "results": results})


@tool
def list_entities(entity_type: str = "") -> str:
    """List all unique entities, optionally filtered by type. Useful to see what/who has been referenced.

    Args:
        entity_type: Filter by type (optional, e.g. "person", "service")
    """
    db = store.connect()
    select = "SELECT entity_type, entity_value, COUNT(*) AS mention_count FROM entities"
    if entity_type:
        results = _rows(
            db,
            f"{select} WHERE entity_type = ? GROUP BY entity_type, entity_value ORDER BY mention_count DESC",
            (entity_type.strip().lower(),),
        )
    else:
        results = _rows(db, f"{select} GROUP BY entity_type, entity_value ORDER BY entity_type, mention_count DESC")
    return _json({"count": len(results), "results": results})


# ─── Thread and timeline tools ───────────────────────────────────────


@tool
def get_thread(thread_id: str) -> str:
    """Get all memories in a conversation thread, in chronological order.

    Args:
        thread_id: The thread ID to retrieve (e.g. "incident-2026-03-24", "stock-analysis-march")
    """
    db = store.connect()
    results = _rows(
        db,
        """SELECT id, topic, content, category, tags, importance, created_at, updated_at
           FROM memories WHERE thread_id = ? ORDER BY created_at""",
        (thread_id,),
    )
    return _json({"thread_id": thread_id, "count": len(results), "results": results})


@tool
def list_threads() -> str:
    """List all conversation threads with their memory counts and latest activity."""
    db = store.connect()
    results = _rows(
        db,
        """SELECT thread_id, COUNT(*) AS memory_count, MIN(created_at) AS first_memory,
                  MAX(updated_at) AS last_activity, GROUP_CONCAT(DISTINCT category) AS categories
           FROM memories WHERE thread_id != '' GROUP BY thread_id ORDER BY last_activity DESC""",
    )
    return _json({"count": len(results), "threads": results})


@tool
def get_daily_summary(date: str = "") -> str:
    """Get memories created or updated on a specific local date, with new ones grouped by category.

    Args:
        date: Date in YYYY-MM-DD format, in this machine's local timezone (default: today)
    """
    try:
        day = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
    except ValueError:
        raise ToolError("Invalid date. Use YYYY-MM-DD") from None
    start = datetime.combine(day, time.min).astimezone().astimezone(timezone.utc).isoformat()
    end = datetime.combine(day + timedelta(days=1), time.min).astimezone().astimezone(timezone.utc).isoformat()

    db = store.connect()
    rows = _rows(
        db,
        """SELECT id, topic, category, tags, importance, thread_id, created_at, updated_at
           FROM memories
           WHERE (created_at >= ? AND created_at < ?) OR (updated_at >= ? AND updated_at < ?)
           ORDER BY category, created_at""",
        (start, end, start, end),
    )
    grouped: dict[str, list[dict[str, Any]]] = {}
    updated = []
    for r in rows:
        if start <= r["created_at"] < end:
            grouped.setdefault(r["category"], []).append(r)
        else:
            updated.append(r)

    return _json(
        {
            "date": day.isoformat(),
            "total": sum(len(v) for v in grouped.values()),
            "by_category": grouped,
            "updated_existing": updated,
        }
    )


@tool
def get_memory_history(memory_id: int) -> str:
    """Get the full edit/append history of a memory, including content replaced by update_memory.

    Args:
        memory_id: The ID of the memory
    """
    db = store.connect()
    row = _get_memory_row(db, memory_id, "id, topic")
    history = _rows(
        db,
        """SELECT action, content_snippet, previous_content, created_at
           FROM memory_history WHERE memory_id = ? ORDER BY created_at""",
        (memory_id,),
    )
    for h in history:
        if not h["previous_content"]:
            h.pop("previous_content")
    return _json({"memory_id": memory_id, "topic": row["topic"], "history_count": len(history), "history": history})


# ─── Maintenance tools ───────────────────────────────────────────────


@tool
def cleanup_expired(dry_run: bool = True) -> str:
    """Find and optionally delete expired memories.

    Args:
        dry_run: If true (default), only lists expired memories without deleting. Set to false to actually delete.
    """
    db = store.connect()
    expired = _rows(db, "SELECT id, topic, category, importance, expires_at FROM memories WHERE is_expired(expires_at)")
    if not expired:
        return _json({"status": "clean", "message": "No expired memories found"})
    if dry_run:
        return _json(
            {
                "status": "dry_run",
                "expired_count": len(expired),
                "expired": expired,
                "message": "Call with dry_run=false to delete these memories",
            }
        )

    deleted_ids = [m["id"] for m in expired]
    db.executemany("DELETE FROM memories WHERE id = ?", [(i,) for i in deleted_ids])
    db.commit()
    return _json({"status": "cleaned", "deleted_count": len(deleted_ids), "deleted_ids": deleted_ids})


@tool
def find_duplicates(topic: str = "", limit: int = 10) -> str:
    """Find potentially duplicate memories. If topic is provided, finds memories similar to it.
    If no topic, finds groups of memories whose topics share most of their significant words.

    Args:
        topic: Topic to check for duplicates (optional — if empty, scans all memories)
        limit: Maximum results or groups (default: 10, max: 100)
    """
    db = store.connect()
    limit = clamp(limit)
    if topic:
        duplicates = find_similar(db, topic, limit)
        return _json({"query_topic": topic, "potential_duplicates": duplicates, "count": len(duplicates)})

    memories = _rows(db, "SELECT id, topic, category, importance, created_at FROM memories ORDER BY created_at")
    groups = group_similar(memories, limit)
    return _json({"duplicate_groups": groups, "group_count": len(groups)})


@tool
def get_stats() -> str:
    """Get overview stats: total memories, breakdown by category, importance, top entities, active threads, expired count."""
    db = store.connect()

    def count(sql: str) -> int:
        return int(db.execute(sql).fetchone()[0])

    return _json(
        {
            "db_path": store.path,
            "total_memories": count("SELECT COUNT(*) FROM memories"),
            "expired_memories": count("SELECT COUNT(*) FROM memories WHERE is_expired(expires_at)"),
            "total_appends": count("SELECT COUNT(*) FROM memory_history WHERE action = 'appended'"),
            "by_category": _rows(db, "SELECT category, COUNT(*) AS c FROM memories GROUP BY category ORDER BY c DESC"),
            "by_importance": _rows(
                db, "SELECT importance, COUNT(*) AS c FROM memories GROUP BY importance ORDER BY c DESC"
            ),
            "top_entities": _rows(
                db,
                """SELECT entity_type, entity_value, COUNT(*) AS c FROM entities
                   GROUP BY entity_type, entity_value ORDER BY c DESC LIMIT 15""",
            ),
            "active_threads": _rows(
                db,
                """SELECT thread_id, COUNT(*) AS c FROM memories WHERE thread_id != ''
                   GROUP BY thread_id ORDER BY MAX(updated_at) DESC LIMIT 10""",
            ),
            "recent_memories": _rows(
                db, "SELECT id, topic, category, importance, created_at FROM memories ORDER BY created_at DESC LIMIT 5"
            ),
        }
    )
