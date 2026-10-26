# Tool reference

agentmemdb exposes 16 MCP tools. Every tool returns a JSON object as text.

- **Errors** come back as `{"error": "..."}` (for example an invalid category or an unknown `memory_id`); nothing is written when a call fails.
- **Timestamps** are ISO 8601 in UTC. `get_daily_summary` takes a date in the machine's local timezone.
- **Expired memories** (past `expires_at`) are hidden from search, listing and entity lookups unless `include_expired` is set.
- **Limits** are clamped: at most 100 results for search and duplicates, 200 for listings.

See [examples.md](examples.md) for real responses.

## Save and edit

### `save_memory`

Save a piece of context/memory for future conversations. Warns about likely duplicates (consider append_memory instead) and adds configured auto-tags.

| Parameter | Type | Default | Description |
|-|-|-|-|
| `topic` | string | required | Short title (e.g. "billing-api Postgres migration decision", "AAPL stock analysis") |
| `content` | string | required | Detailed context to remember — include conclusions, data, links, action items |
| `category` | string | `"other"` | One of: conversation, decision, incident, research, person, project, howto, config, other |
| `tags` | string | `""` | Comma-separated tags (e.g. "postgres,database,billing") |
| `importance` | string | `"normal"` | One of: low, normal, high, critical |
| `source` | string | `""` | Where this came from (default: the connected client's name, e.g. "claude-code") |
| `thread_id` | string | `""` | Link related memories together with the same thread ID (e.g. "incident-2026-03-24") |
| `entities` | string | `""` | JSON array of objects, e.g. [{"type":"service","value":"billing-api"},{"type":"person","value":"alice"}] |
| `expires_at` | string | `""` | Optional expiry date (YYYY-MM-DD) after which this memory is less relevant |

### `append_memory`

Append additional context to an existing memory without replacing it. The new content is added with a timestamp separator. History is tracked.

| Parameter | Type | Default | Description |
|-|-|-|-|
| `memory_id` | integer | required | The ID of the memory to append to |
| `content` | string | required | New content to add (will be appended with a timestamp) |
| `source` | string | `""` | Where this update came from (default: the connected client's name) |

### `update_memory`

Update an existing memory. Only provided fields are updated. Use append_memory to add context without replacing. Replaced content is kept in the memory's history (see get_memory_history).

| Parameter | Type | Default | Description |
|-|-|-|-|
| `memory_id` | integer | required | The ID of the memory to update |
| `topic` | string | `""` | New topic (leave empty to keep existing) |
| `content` | string | `""` | New content (leave empty to keep existing) |
| `category` | string | `""` | New category (leave empty to keep existing) |
| `tags` | string | `""` | New tags (leave empty to keep existing) |
| `importance` | string | `""` | New importance (leave empty to keep existing) |
| `thread_id` | string | `""` | New thread ID (leave empty to keep existing) |
| `expires_at` | string | `""` | New expiry (leave empty to keep existing) |

### `delete_memory`

Delete a memory and its linked entities.

| Parameter | Type | Default | Description |
|-|-|-|-|
| `memory_id` | integer | required | The ID of the memory to delete |

## Search and read

### `search_memory`

Search memories by relevance: full-text search with stemming (topic and tag matches rank highest), falling back to substring matching. Returns a snippet per memory; use get_memory for the full text. Expired memories are excluded by default.

| Parameter | Type | Default | Description |
|-|-|-|-|
| `query` | string | required | Search query — plain words, hyphenated names, IDs, or FTS5 syntax (e.g. "tags:aws", "datadog OR sentry") |
| `category` | string | `""` | Filter by category (optional) |
| `importance` | string | `""` | Filter by minimum importance: low, normal, high, critical (optional) |
| `limit` | integer | `10` | Maximum number of results (default: 10, max: 100) |
| `include_expired` | boolean | `false` | Set to true to include expired memories (default: false) |
| `full_content` | boolean | `false` | Set to true to return full content instead of snippets (default: false) |

### `list_memories`

List saved memories with optional filters. Expired memories excluded by default.

| Parameter | Type | Default | Description |
|-|-|-|-|
| `category` | string | `""` | Filter by category (optional) |
| `tag` | string | `""` | Filter by tag (optional) |
| `thread_id` | string | `""` | Filter by thread ID to see all related memories (optional) |
| `limit` | integer | `25` | Maximum number of results (default: 25, max: 200) |
| `include_expired` | boolean | `false` | Set to true to include expired memories (default: false) |

### `get_memory`

Get the full content of a specific memory including linked entities and edit history.

| Parameter | Type | Default | Description |
|-|-|-|-|
| `memory_id` | integer | required | The ID of the memory to retrieve |

### `get_memory_history`

Get the full edit/append history of a memory, including content replaced by update_memory.

| Parameter | Type | Default | Description |
|-|-|-|-|
| `memory_id` | integer | required | The ID of the memory |

## Entities

### `find_by_entity`

Find all memories linked to a specific entity (person, service, account, etc.).

| Parameter | Type | Default | Description |
|-|-|-|-|
| `entity_type` | string | `""` | Type of entity (e.g. "person", "service", "account", "bucket", "ticket") |
| `entity_value` | string | `""` | Value to search, substring match (e.g. "alice", "billing-api", "prod-db") |
| `limit` | integer | `25` | Maximum results (default: 25, max: 200) |

### `list_entities`

List all unique entities, optionally filtered by type. Useful to see what/who has been referenced.

| Parameter | Type | Default | Description |
|-|-|-|-|
| `entity_type` | string | `""` | Filter by type (optional, e.g. "person", "service") |

## Threads and timeline

### `get_thread`

Get all memories in a conversation thread, in chronological order.

| Parameter | Type | Default | Description |
|-|-|-|-|
| `thread_id` | string | required | The thread ID to retrieve (e.g. "incident-2026-03-24", "stock-analysis-march") |

### `list_threads`

List all conversation threads with their memory counts and latest activity.

### `get_daily_summary`

Get memories created or updated on a specific local date, with new ones grouped by category.

| Parameter | Type | Default | Description |
|-|-|-|-|
| `date` | string | `""` | Date in YYYY-MM-DD format, in this machine's local timezone (default: today) |

## Maintenance

### `find_duplicates`

Find potentially duplicate memories. If topic is provided, finds memories similar to it. If no topic, finds groups of memories whose topics share most of their significant words.

| Parameter | Type | Default | Description |
|-|-|-|-|
| `topic` | string | `""` | Topic to check for duplicates (optional — if empty, scans all memories) |
| `limit` | integer | `10` | Maximum results or groups (default: 10, max: 100) |

### `cleanup_expired`

Find and optionally delete expired memories.

| Parameter | Type | Default | Description |
|-|-|-|-|
| `dry_run` | boolean | `true` | If true (default), only lists expired memories without deleting. Set to false to actually delete. |

### `get_stats`

Get overview stats: total memories, breakdown by category, importance, top entities, active threads, expired count.
