# Getting started

## Requirements

- Python 3.10 or newer
- macOS or Linux
- An MCP client: Claude Code, omp, Claude Desktop, Cursor, VS Code, Codex, or any other

## Install

Pick one:

| Method | Command | Upgrade with |
|-|-|-|
| Homebrew | `brew install harsh-gulhane/tap/agentmemdb` | `brew upgrade agentmemdb` |
| pipx | `pipx install agentmemdb` | `pipx upgrade agentmemdb` |
| pip | `pip install agentmemdb` (into the current environment) | `pip install -U agentmemdb` |
| uv, no install | `uvx agentmemdb` runs it in a cached environment | `uvx agentmemdb@latest` |
| From source | `uvx --from git+https://github.com/harsh-gulhane/agentmemdb agentmemdb` | |

Check it works with `agentmemdb --version`.

The client examples below use `uvx agentmemdb`, which works without installing anything. If you installed with Homebrew, pipx or pip, use the plain `agentmemdb` command instead (in JSON configs: `"command": "agentmemdb"` and no `args`).

## Connect your clients

Name the server `memory` in every client. The tool names then match everywhere (`mcp__memory__search_memory` in Claude Code, for example), and so do your instructions files.

All clients below start their own `agentmemdb` process over stdio. They share memories because every process opens the same database file; see [configuration.md](configuration.md#sharing-one-database-across-agents).

### Claude Code

```sh
claude mcp add memory -s user -- uvx agentmemdb
```

`-s user` makes it available in every project. Run `/mcp` in a session to check it is connected.

### omp

Add to `~/.omp/agent/mcp.json`. omp does not import Claude Code's user-level MCP servers by default, so it needs its own entry:

```json
{
  "mcpServers": {
    "memory": { "type": "stdio", "command": "uvx", "args": ["agentmemdb"] }
  }
}
```

### Claude Desktop

Edit `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "memory": { "command": "uvx", "args": ["agentmemdb"] }
  }
}
```

Desktop apps don't always see your shell's `PATH`. If the server fails to start, use the absolute path from `which uvx` (or `which agentmemdb`) as the command.

### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "memory": { "command": "uvx", "args": ["agentmemdb"] }
  }
}
```

### VS Code

Add to `.vscode/mcp.json` in a workspace, or run **MCP: Open User Configuration** for all workspaces:

```json
{
  "servers": {
    "memory": { "type": "stdio", "command": "uvx", "args": ["agentmemdb"] }
  }
}
```

### Codex CLI

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.memory]
command = "uvx"
args = ["agentmemdb"]
```

### Any other client, or one shared server over HTTP

Use the stdio command `uvx agentmemdb`. Or run a single long-lived server and point HTTP-capable clients at it:

```sh
agentmemdb --transport http --port 8765
# endpoint: http://127.0.0.1:8765/mcp
```

The HTTP server listens on 127.0.0.1 only and has no authentication; see [SECURITY.md](../SECURITY.md).

## Verify

```sh
agentmemdb --check
```

prints the version, the database and config paths it resolved, and whether they exist. Then ask an agent:

> Which memory database are you connected to?

It calls `get_stats`, whose `db_path` should match `--check` in every client.

## Next steps

- Make agents save and search on their own with a [memory policy](../examples/memory-policy.md)
- Add [auto-tag rules and shared instructions](configuration.md)
- See [real example sessions](examples.md)
