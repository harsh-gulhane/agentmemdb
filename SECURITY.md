# Security policy

## Supported versions

Security fixes are released for the latest minor version.

| Version | Supported |
|-|-|
| 0.1.x | Yes |

## Reporting a vulnerability

Please do not open a public issue. Report it privately through [GitHub security advisories](https://github.com/harsh-gulhane/agentmemdb/security/advisories/new) with steps to reproduce and the affected version (`agentmemdb --version`). You should get a first response within a week.

## Security model

agentmemdb is a local tool. Know these properties before you store anything sensitive:

- **No network calls.** The server never contacts external services and sends no telemetry.
- **Plaintext storage.** Memories are stored unencrypted in a SQLite file. A database directory that agentmemdb creates gets mode `0700`, so other users on the machine can't read it, but any process running as your user can. Use disk encryption, and don't store secrets such as passwords, tokens or private keys.
- **Every connected agent has full access.** Any MCP client you connect can read, change and delete every memory.
- **Treat memories as untrusted input.** Memories are text written by agents, which may have been influenced by the content they processed. An agent that recalls a memory should treat its content as data, not as instructions. This matters most when agents with different permissions share one database.
- **HTTP transport.** `--transport http` listens on 127.0.0.1 only, with DNS rebinding protection, but has no authentication: any local process can connect. Prefer stdio, and never expose the HTTP port beyond localhost.
