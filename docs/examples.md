# Examples

A walkthrough of Claude Code and omp sharing one agentmemdb database, set up with [`examples/config.json`](../examples/config.json).

The tool calls and responses are real, captured from agentmemdb 0.1.0. The prompts show the kind of request that leads an agent to make each call. Responses are pretty-printed here (the server returns compact JSON), and long values are trimmed where marked `…`.

## 1. Save a decision (Claude Code)

> **You:** We decided to move billing-api from MySQL to Postgres 17 in Q1, because we need row-level security to isolate merchants. Alice owns it, and the cutover needs a 30-minute write freeze. Remember this.

Claude Code calls `save_memory`:

```json
{
  "topic": "billing-api: move from MySQL to Postgres 17",
  "content": "Decision: migrate billing-api to Postgres 17 in Q1. Reason: we need row-level security to isolate merchants, which MySQL does not offer. Alice owns the migration; cutover needs a 30-minute write freeze.",
  "category": "decision",
  "importance": "high",
  "tags": "billing",
  "thread_id": "billing-db-migration",
  "entities": "[{\"type\":\"service\",\"value\":\"billing-api\"},{\"type\":\"person\",\"value\":\"alice\"}]"
}
```

Response:

```json
{
  "status": "saved",
  "id": 1,
  "topic": "billing-api: move from MySQL to Postgres 17",
  "category": "decision",
  "tags": "billing,database",
  "auto_tags_added": ["database"]
}
```

The `database` tag came from the auto-tag rule `"database": "postgres|mysql|sqlite|redis"` in the config.

## 2. Recall it from another agent (omp)

> **You, in omp the next day:** Why are we moving billing to Postgres?

omp calls `search_memory` with `{"query": "why are we moving billing to postgres"}`:

```json
{
  "count": 1,
  "results": [
    {
      "id": 1,
      "topic": "billing-api: move from MySQL to Postgres 17",
      "category": "decision",
      "tags": "billing,database",
      "importance": "high",
      "thread_id": "billing-db-migration",
      "expires_at": "",
      "created_at": "2026-10-25T23:39:32.044150+00:00",
      "updated_at": "2026-10-25T23:39:32.044150+00:00",
      "content_length": 202,
      "snippet": "…migrate billing-api to Postgres 17 in Q1. Reason: we need row-level security to isolate merchants, which MySQL does not offer. Alice owns the migration; cutover needs a 30-minute write…"
    }
  ]
}
```

Plain questions work. No memory contains every word of the question, so search falls back to matching any term, ranked with topic and tag matches first. Results carry a snippet rather than the full text, which keeps responses small; the agent calls `get_memory` when it needs more.

## 3. Add context (omp)

> **You:** The staging dry run passed: 41 GB copied in 18 minutes, no row-level security errors. Add that to the migration decision.

omp calls `append_memory` with `{"memory_id": 1, "content": "Dry run on staging passed: 41 GB copied in 18 minutes with no row-level security errors."}`:

```json
{
  "status": "appended",
  "id": 1,
  "topic": "billing-api: move from MySQL to Postgres 17",
  "total_appends": 1,
  "new_tags": null
}
```

## 4. Read the full memory with attribution (Claude Code)

> **You, back in Claude Code:** Where are we with the billing migration?

Claude Code calls `get_memory` with `{"memory_id": 1}`:

```json
{
  "id": 1,
  "topic": "billing-api: move from MySQL to Postgres 17",
  "content": "Decision: migrate billing-api to Postgres 17 in Q1. Reason: we need row-level security to isolate merchants, which MySQL does not offer. Alice owns the migration; cutover needs a 30-minute write freeze.\n\n---\n**[Update 2026-10-25 23:39 UTC]** *(from omp)*\nDry run on staging passed: 41 GB copied in 18 minutes with no row-level security errors.",
  "category": "decision",
  "tags": "billing,database",
  "importance": "high",
  "source": "claude-code",
  "thread_id": "billing-db-migration",
  "expires_at": "",
  "created_at": "2026-10-25T23:39:32.044150+00:00",
  "updated_at": "2026-10-25T23:39:32.368604+00:00",
  "is_expired": false,
  "entities": [
    { "entity_type": "service", "entity_value": "billing-api" },
    { "entity_type": "person", "entity_value": "alice" }
  ],
  "history": [
    { "action": "created", "content_snippet": "Decision: migrate billing-api to Postgres 17 in Q1. Reason: we need row-level security to isolate me", "created_at": "2026-10-25T23:39:32.044150+00:00" },
    { "action": "appended", "content_snippet": "Dry run on staging passed: 41 GB copied in 18 minutes with no row-level security errors.", "created_at": "2026-10-25T23:39:32.368604+00:00" }
  ]
}
```

`source` records that Claude Code created the memory, and the update is marked *(from omp)*. Neither client was told its name; agentmemdb takes it from the MCP handshake.

## 5. Duplicate warning

> **You:** Save the cutover plan: Saturday 02:00 UTC with a 30-minute write freeze.

Claude Code calls `save_memory` with `{"topic": "billing-api Postgres 17 migration cutover plan", "content": "Cutover Saturday 02:00 UTC with a 30-minute write freeze.", "category": "project", "thread_id": "billing-db-migration"}`:

```json
{
  "status": "saved",
  "id": 2,
  "topic": "billing-api Postgres 17 migration cutover plan",
  "category": "project",
  "tags": "database",
  "auto_tags_added": ["database"],
  "possible_duplicates": [
    { "id": 1, "topic": "billing-api: move from MySQL to Postgres 17", "exact_match": false }
  ]
}
```

The memory is saved, and the warning lets the agent decide whether `append_memory` would have been the better choice next time.

## 6. Follow a thread

> **You:** Show me everything about the billing database migration, in order.

`get_thread` with `{"thread_id": "billing-db-migration"}`:

```json
{
  "thread_id": "billing-db-migration",
  "count": 2,
  "results": [
    { "id": 1, "topic": "billing-api: move from MySQL to Postgres 17", "content": "Decision: migrate billing-api to Postgres 17 in Q1. …", "category": "decision", "tags": "billing,database", "importance": "high", "created_at": "2026-10-25T23:39:32.044150+00:00", "updated_at": "2026-10-25T23:39:32.368604+00:00" },
    { "id": 2, "topic": "billing-api Postgres 17 migration cutover plan", "content": "Cutover Saturday 02:00 UTC with a 30-minute write freeze.", "category": "project", "tags": "database", "importance": "normal", "created_at": "2026-10-25T23:39:32.676363+00:00", "updated_at": "2026-10-25T23:39:32.676363+00:00" }
  ]
}
```

## 7. Look up by entity

> **You:** What is Alice working on?

`find_by_entity` with `{"entity_type": "person", "entity_value": "alice"}`:

```json
{
  "count": 1,
  "results": [
    { "id": 1, "topic": "billing-api: move from MySQL to Postgres 17", "category": "decision", "tags": "billing,database", "importance": "high", "thread_id": "billing-db-migration", "expires_at": "", "created_at": "2026-10-25T23:39:32.044150+00:00" }
  ]
}
```

## 8. Confirm which database an agent uses

> **You:** Which memory database are you connected to?

`get_stats` (trimmed):

```json
{
  "db_path": "/Users/you/.local/share/agentmemdb/memory.db",
  "total_memories": 2,
  "expired_memories": 0,
  "total_appends": 1,
  "by_category": [{ "category": "decision", "c": 1 }, { "category": "project", "c": 1 }],
  "active_threads": [{ "thread_id": "billing-db-migration", "c": 2 }],
  "…": "…"
}
```

From a terminal, `agentmemdb --check` shows the same resolution without starting the server:

```console
$ agentmemdb --check
{
  "version": "0.1.0",
  "db_path": "/Users/you/.local/share/agentmemdb/memory.db",
  "db_exists": true,
  "config_path": "/Users/you/.config/agentmemdb/config.json",
  "config_found": true,
  "auto_tags": 5
}
```

## Prompts that work well

| Ask the agent | Tools it reaches for |
|-|-|
| "Remember that …" / "Note this decision: …" | `save_memory` |
| "What do we know about billing-api?" | `search_memory`, `find_by_entity` |
| "Add to the migration note that …" | `append_memory` |
| "Correct the cutover time in that memory to 03:00 UTC" | `update_memory` (the old text stays in history) |
| "What did I work on yesterday?" | `get_daily_summary` |
| "Show the whole billing-db-migration thread" | `get_thread`, `list_threads` |
| "Find duplicate memories and merge them" | `find_duplicates`, `append_memory`, `delete_memory` |
| "Clean up expired memories" | `cleanup_expired` (dry run first) |
| "Which memory database are you using?" | `get_stats` |

To make agents save and search without being asked, add a memory policy: see [`examples/memory-policy.md`](../examples/memory-policy.md).
