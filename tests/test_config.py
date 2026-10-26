"""Settings resolution and config validation."""

import json
from pathlib import Path

import pytest

from agentmemdb import server
from agentmemdb.config import BASE_INSTRUCTIONS, ConfigError, config_path, default_db_path, load_settings


def test_server_uses_test_config() -> None:
    assert set(server.settings.auto_tags) == {"datadog", "github"}
    assert server.settings.instructions.startswith(BASE_INSTRUCTIONS)
    assert server.settings.instructions.endswith("Test policy: always save.")


def test_default_db_path_follows_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert default_db_path() == str(tmp_path / ".local/share/agentmemdb/memory.db")
    monkeypatch.setenv("XDG_DATA_HOME", "")
    assert default_db_path() == str(tmp_path / ".local/share/agentmemdb/memory.db")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert default_db_path() == str(tmp_path / "xdg/agentmemdb/memory.db")


def test_config_path_follows_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTMEMDB_CONFIG")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    assert config_path() == str(tmp_path / ".config/agentmemdb/config.json")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert config_path() == str(tmp_path / "xdg/agentmemdb/config.json")


def test_db_path_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"db_path": "~/from-config.db"}))
    monkeypatch.setenv("AGENTMEMDB_CONFIG", str(config))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENTMEMDB_DB_PATH", str(tmp_path / "from-env.db"))
    assert load_settings().db_path == str(tmp_path / "from-env.db")
    monkeypatch.delenv("AGENTMEMDB_DB_PATH")
    assert load_settings().db_path == str(tmp_path / "from-config.db")
    config.write_text("{}")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert load_settings().db_path == str(tmp_path / "data/agentmemdb/memory.db")


def test_missing_config_uses_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTMEMDB_CONFIG", str(tmp_path / "absent.json"))
    settings = load_settings()
    assert settings.config_found is False
    assert settings.auto_tags == {}
    assert settings.instructions == BASE_INSTRUCTIONS


def test_tags_for_matches_lowercased_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"auto_tags": {"k8s": "kubernetes|k8s", "aws": r"\baws\b"}}))
    monkeypatch.setenv("AGENTMEMDB_CONFIG", str(config))
    settings = load_settings()
    assert settings.tags_for("Upgraded K8S nodes", "on AWS") == ["k8s", "aws"]
    assert settings.tags_for("laws") == []


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("{not json", "cannot read config file"),
        ("[]", "must contain a JSON object"),
        ('{"db_path": 1}', "'db_path' must be a string"),
        ('{"instructions": ["x"]}', "'instructions' must be a string"),
        ('{"auto_tags": ["aws"]}', '"auto_tags" must be an object'),
        ('{"auto_tags": {"aws": 1}}', "must be a regex string"),
        ('{"auto_tags": {"aws": "("}}', "is not a valid regex"),
    ],
)
def test_invalid_config_raises_clear_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str, message: str
) -> None:
    config = tmp_path / "config.json"
    config.write_text(content)
    monkeypatch.setenv("AGENTMEMDB_CONFIG", str(config))
    with pytest.raises(ConfigError, match=message.replace("(", r"\(").replace("[", r"\[")):
        load_settings()
