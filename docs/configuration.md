# Configuration

Everything is optional. With no configuration, agentmemdb stores its database at `~/.local/share/agentmemdb/memory.db`.

## Environment variables

| Variable | Purpose |
|-|-|
| `AGENTMEMDB_DB_PATH` | Database file. Overrides `db_path` in the config file. |
| `AGENTMEMDB_CONFIG` | Config file location. Default: `$XDG_CONFIG_HOME/agentmemdb/config.json`, i.e. `~/.config/agentmemdb/config.json`. |
| `XDG_DATA_HOME` | Base directory for the default database. Default: `~/.local/share`. |
| `XDG_CONFIG_HOME` | Base directory for the default config file. Default: `~/.config`. |

Empty variables are treated as unset. `~` is expanded in all paths.

## Config file

A JSON object with any of these keys ([`examples/config.json`](../examples/config.json) is a complete example):

```json
{
  "db_path": "~/.local/share/agentmemdb/memory.db",
  "auto_tags": {
    "database": "postgres|mysql|sqlite|redis",
    "kubernetes": "kubernetes|k8s",
    "incident": "incident|outage|breach"
  },
  "instructions": "Search memory before answering questions about past work. Save decisions with their reasons."
}
```

| Key | Type | Purpose |
|-|-|-|
| `db_path` | string | Database file. |
| `auto_tags` | object | `{"tag": "regex"}`. A memory gets the tag when the pattern matches its topic or content (lowercased, Python regex syntax). Applied on `save_memory` and `append_memory`. |
| `instructions` | string | Appended to the server's built-in instructions. MCP clients put server instructions into the agent's system prompt, so this is the place for a memory policy that every client should follow. |

agentmemdb validates the file at startup. A malformed file stops the server with a message naming the problem, for example:

```console
$ agentmemdb --check
agentmemdb: error: config file /Users/you/.config/agentmemdb/config.json: auto_tags['k8s'] is not a valid regex: missing ), unterminated subpattern at position 0
```

Clients read the config when they start the server, so reconnect them after a change (`/mcp` in Claude Code and omp).

## Sharing one database across agents

Every process that resolves to the same database file shares the same memories. The path is chosen in this order:

1. `AGENTMEMDB_DB_PATH`
2. `db_path` in the config file
3. `$XDG_DATA_HOME/agentmemdb/memory.db` (default `~/.local/share/agentmemdb/memory.db`)

Set it in one place, the config file or nowhere, rather than per client, so clients can't drift apart. To confirm:

- `agentmemdb --check` prints the database and config the server resolves to.
- The `get_stats` tool reports `db_path`, so any agent can tell you which database it is using.
- Each memory records the client that saved it (`source`, such as `claude-code` or `omp`), and appends are marked with the client that made them.

## Using an existing database

Point `db_path` at the file. Databases created by earlier versions are upgraded in place on first start (the schema version is kept in `PRAGMA user_version`). Back the file up first: upgrades are one-way.

```sh
sqlite3 ~/.local/share/agentmemdb/memory.db ".backup '/tmp/memory-backup.db'"
```

## Backups

The database is one SQLite file in WAL mode. Use SQLite's online backup, which is safe while agents are connected:

```sh
sqlite3 ~/.local/share/agentmemdb/memory.db ".backup '$HOME/memory-$(date +%F).db'"
```

Copying `memory.db` with `cp` while a client is writing can miss recent changes that are still in `memory.db-wal`.
