# Contributing

Thanks for your interest in agentmemdb. Bug reports, ideas and pull requests are welcome.

## Development setup

You need [uv](https://docs.astral.sh/uv/) and `make`.

```sh
git clone https://github.com/harsh-gulhane/agentmemdb && cd agentmemdb
make install      # creates .venv with an editable install and the dev tools
make check        # lint, type-check and test: the same checks CI runs
```

Without uv: `python -m venv .venv && .venv/bin/pip install -e . --group dev` (pip 25.1 or newer).

| Command | What it does |
|-|-|
| `make lint` | `ruff check` and `ruff format --check` |
| `make format` | Fix lint issues and format the code |
| `make typecheck` | `mypy` in strict mode |
| `make test` | `pytest`, including end-to-end stdio and HTTP sessions |
| `make cov` | Tests with a coverage report |
| `make build` | Build the sdist and wheel and validate them with `twine check` |

Optional: `uv tool install pre-commit && pre-commit install` runs ruff and basic file checks on every commit.

## Project layout

```text
src/agentmemdb/
  cli.py        command-line entry point
  config.py     settings from environment variables and the config file
  server.py     FastMCP app and the 16 tools
  storage.py    SQLite connections, schema, migrations
  search.py     FTS5 search, substring fallback, duplicate detection
  models.py     categories, importance levels, input validation
tests/          pytest suite; test_e2e.py drives real MCP sessions
scripts/        release.sh and update-formula.sh for maintainers
docs/           user documentation and logo assets
examples/       example config and memory policy prompt
```

[docs/architecture.md](docs/architecture.md) explains how the pieces fit together.

## Guidelines

- **Keep it small.** The only runtime dependency is `mcp`. Discuss new dependencies in an issue first.
- **Test every change.** Tests use a fresh temporary database per test and never touch your real memory database.
- **Keep tool contracts stable.** Tool names, parameters and response fields are an API that agents and instructions files depend on. Additive changes are fine; renames and removals need a deprecation path and a changelog entry.
- **Schema changes need a migration.** Bump `SCHEMA_VERSION` in `storage.py`, add an idempotent migration step, and add a test that upgrades a database from the previous version.
- **Tool docstrings are prompts.** Agents read them to decide which tool to call, so keep them accurate and concise.

## Pull requests

1. Branch from `main`.
2. Make the change with tests, and run `make check`.
3. Add a line under **Unreleased** in [CHANGELOG.md](CHANGELOG.md) for user-visible changes.
4. Use short, imperative commit messages, e.g. `Add tag filter to search_memory`.
5. Open the pull request and describe what changed and why.

## Releasing

Maintainers only. Releases are published from GitHub Actions with PyPI trusted publishing, so no PyPI token is stored anywhere.

1. Set `__version__` in `src/agentmemdb/__init__.py`, move the **Unreleased** changelog entries under `## [x.y.z] - <date>`, and merge to `main`.
2. On an up-to-date `main`, run `scripts/release.sh x.y.z`. It:
   - tags `vx.y.z` and pushes the tag;
   - waits for the [release workflow](.github/workflows/release.yml), which tests, builds, uploads to PyPI and creates the GitHub release with the changelog notes;
   - runs `scripts/update-formula.sh`, which points the Homebrew formula in [harsh-gulhane/homebrew-tap](https://github.com/harsh-gulhane/homebrew-tap) at the new version, refreshes its Python resources, installs and tests it, and pushes.

Dependabot opens weekly pull requests for new versions of Python packages, GitHub Actions and pre-commit hooks; CI must pass before merging them.
