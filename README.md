<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo-wordmark-dark.svg">
    <img alt="agentmemdb" src="docs/assets/logo-wordmark-light.svg" width="420">
  </picture>
</p>

<p align="center">
  <strong>Local-first, shared long-term memory for AI agents.</strong><br>
  One SQLite database, served over MCP, so Claude Code, omp and every other agent on your machine remember the same things.
</p>

<p align="center">
  <a href="https://github.com/harsh-gulhane/agentmemdb/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/harsh-gulhane/agentmemdb/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="MCP server" src="https://img.shields.io/badge/MCP-server-7C3AED">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue"></a>
</p>

<p align="center">
  <a href="docs/getting-started.md">Getting started</a> ·
  <a href="docs/examples.md">Examples</a> ·
  <a href="docs/configuration.md">Configuration</a> ·
  <a href="docs/tools.md">Tools</a> ·
  <a href="docs/architecture.md">Architecture</a>
</p>

---

AI agents forget everything when a session ends, and different agents never see what the others learned. agentmemdb gives them one long-term memory: a local SQLite file, exposed as 16 MCP tools, that every agent on your machine reads and writes.

- **Shared.** What Claude Code saves in the morning, omp can recall in the afternoon. Every write records which agent made it.
- **Local.** One file on your machine. No cloud service, no API keys, no embedding model, no telemetry.
- **Cheap to recall.** Ranked full-text search returns short snippets instead of whole memories, so lookups use few tokens.
- **Safe with many agents.** Concurrent readers and writers, and a failed call can never leave the database locked.

## See it in action

```text
You → Claude Code   We're moving billing-api from MySQL to Postgres 17 for row-level security. Remember that.

      save_memory   {"topic": "billing-api: move from MySQL to Postgres 17", "category": "decision", "importance": "high", …}
                  ← {"status": "saved", "id": 1, "tags": "billing,database", "auto_tags_added": ["database"]}

You → omp           (next day) Why are we moving billing to Postgres?

      search_memory {"query": "why are we moving billing to postgres"}
                  ← {"count": 1, "results": [{"id": 1, "topic": "billing-api: move from MySQL to Postgres 17",
                       "snippet": "…we need row-level security to isolate merchants, which MySQL does not offer…"}]}
```

The [examples](docs/examples.md) walk through the full session: appending from a second agent, attribution, duplicate warnings, threads and entities, with real responses.

## Quick start

Install it with any of these (macOS or Linux, Python 3.10+):

```sh
brew install harsh-gulhane/tap/agentmemdb   # Homebrew
pipx install agentmemdb                     # or: pip install agentmemdb
uvx agentmemdb --check                      # or run it without installing, with uv
```

`agentmemdb --check` shows where the database and config will live. Then connect your agents, using the server name `memory` everywhere so tool names match across clients (with uv, replace `agentmemdb` with `uvx agentmemdb`):

```sh
# Claude Code
claude mcp add memory -s user -- agentmemdb
```

```jsonc
// omp: ~/.omp/agent/mcp.json
{ "mcpServers": { "memory": { "type": "stdio", "command": "agentmemdb" } } }
```

Claude Desktop, Cursor, VS Code, Codex and HTTP setups are in [getting started](docs/getting-started.md). To have agents save and search without being asked, add the [memory policy prompt](examples/memory-policy.md) to your `CLAUDE.md` or `AGENTS.md`.

## Features

- **Relevance search.** SQLite FTS5 with stemming and BM25 ranking, where topic and tag matches rank highest. Handles IDs and names like `OPS-2406`, `PR #3056` and `example.com`, plain questions, and partial words.
- **Structured memories.** Categories, importance levels, tags, threads, entities (people, services, repos, tickets) and expiry dates.
- **Automatic tags.** Regex rules in the config tag matching memories, e.g. anything mentioning Postgres or MySQL gets `database`.
- **Safe edits.** Duplicate warnings on save, append mode, and an edit history that keeps replaced content.
- **One policy for every agent.** Instructions in the config file reach every connected client's system prompt.
- **stdio or HTTP.** One process per client, or one shared server over streamable HTTP on localhost.

## Tools

| Area | Tools |
|-|-|
| Save and edit | `save_memory`, `append_memory`, `update_memory`, `delete_memory` |
| Search and read | `search_memory`, `list_memories`, `get_memory`, `get_memory_history` |
| Entities | `find_by_entity`, `list_entities` |
| Threads and timeline | `get_thread`, `list_threads`, `get_daily_summary` |
| Maintenance | `find_duplicates`, `cleanup_expired`, `get_stats` |

Parameters and behaviour: [tool reference](docs/tools.md).

## Configuration

Optional. `~/.config/agentmemdb/config.json`:

```json
{
  "db_path": "~/.local/share/agentmemdb/memory.db",
  "auto_tags": { "database": "postgres|mysql|sqlite", "incident": "incident|outage" },
  "instructions": "Search memory before answering questions about past work."
}
```

Environment variables, path resolution, sharing and backups: [configuration](docs/configuration.md).

## Development

```sh
git clone https://github.com/harsh-gulhane/agentmemdb && cd agentmemdb
make install    # uv sync: editable install plus dev tools
make check      # ruff, mypy --strict, pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the project layout and workflow.

## Security

agentmemdb stores memories unencrypted in a local file and makes no network calls. Read [SECURITY.md](SECURITY.md) for the security model, and report vulnerabilities privately through GitHub security advisories.

## License

[MIT](LICENSE) © Harsh Gulhane
