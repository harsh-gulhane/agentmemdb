# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-26

First public release.

### Added

- 16 MCP tools to save, search, append, update, link and review memories
- SQLite FTS5 search with stemming, BM25 ranking, snippets and a substring fallback
- Duplicate warnings, automatic tags, threads, entities, expiry and edit history
- One database shared by every MCP client on the machine; each write records which client made it
- Optional JSON config for the database path, auto-tag rules and agent instructions, with clear errors for invalid values
- stdio and streamable HTTP transports; `--check` and `--version` flags
- Server name, version and icon reported to MCP clients

[Unreleased]: https://github.com/harsh-gulhane/agentmemdb/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/harsh-gulhane/agentmemdb/releases/tag/v0.1.0
