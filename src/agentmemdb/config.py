"""Settings resolved from environment variables and the optional JSON config file."""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

APP_NAME = "agentmemdb"

BASE_INSTRUCTIONS = (
    "Long-term memory that persists across sessions and is shared by every agent connected to it. "
    "Search it (search_memory, find_by_entity, get_thread) when past context could help, and save decisions, "
    "findings and facts worth keeping with save_memory; prefer append_memory over saving a near-duplicate. "
    "search_memory returns snippets; use get_memory (or full_content=true) for the full text. "
    'Pass save_memory entities as a JSON array of objects, e.g. [{"type":"service","value":"billing-api"}].'
)


class ConfigError(ValueError):
    """The config file exists but cannot be used."""


@dataclass(frozen=True)
class Settings:
    db_path: str
    config_path: str
    config_found: bool = False
    auto_tags: dict[str, re.Pattern[str]] = field(default_factory=dict)
    instructions: str = BASE_INSTRUCTIONS

    def tags_for(self, *texts: str) -> list[str]:
        """Auto-tags whose pattern matches the given texts (lowercased)."""
        text = " ".join(texts).lower()
        return [tag for tag, pattern in self.auto_tags.items() if pattern.search(text)]


def config_path() -> str:
    """AGENTMEMDB_CONFIG, else $XDG_CONFIG_HOME/agentmemdb/config.json."""
    return os.path.expanduser(
        os.environ.get("AGENTMEMDB_CONFIG")
        or os.path.join(os.environ.get("XDG_CONFIG_HOME") or "~/.config", APP_NAME, "config.json")
    )


def default_db_path() -> str:
    """$XDG_DATA_HOME/agentmemdb/memory.db (default ~/.local/share/agentmemdb/memory.db)."""
    return os.path.join(os.path.expanduser(os.environ.get("XDG_DATA_HOME") or "~/.local/share"), APP_NAME, "memory.db")


def load_settings() -> Settings:
    """Resolve settings; the database path is AGENTMEMDB_DB_PATH, then config db_path, then the default."""
    path = config_path()
    found = os.path.exists(path)
    config = _read_config(path) if found else {}
    db_path = os.environ.get("AGENTMEMDB_DB_PATH") or config.get("db_path") or default_db_path()
    extra = config.get("instructions", "")
    return Settings(
        db_path=os.path.expanduser(db_path),
        config_path=path,
        config_found=found,
        auto_tags=_compile_auto_tags(path, config.get("auto_tags", {})),
        instructions="\n".join(filter(None, [BASE_INSTRUCTIONS, extra])),
    )


def _read_config(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError) as err:
        raise ConfigError(f"cannot read config file {path}: {err}") from err
    if not isinstance(config, dict):
        raise ConfigError(f"config file {path} must contain a JSON object")
    for key in ("db_path", "instructions"):
        if not isinstance(config.get(key, ""), str):
            raise ConfigError(f"config file {path}: {key!r} must be a string")
    return config


def _compile_auto_tags(path: str, auto_tags: Any) -> dict[str, re.Pattern[str]]:
    if not isinstance(auto_tags, dict):
        raise ConfigError(f'config file {path}: "auto_tags" must be an object of {{"tag": "regex"}}')
    compiled = {}
    for tag, pattern in auto_tags.items():
        if not isinstance(pattern, str):
            raise ConfigError(f"config file {path}: auto_tags[{tag!r}] must be a regex string")
        try:
            compiled[tag] = re.compile(pattern)
        except re.error as err:
            raise ConfigError(f"config file {path}: auto_tags[{tag!r}] is not a valid regex: {err}") from err
    return compiled
