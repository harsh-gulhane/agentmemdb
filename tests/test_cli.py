"""The command-line entry point, in process."""

import json
from pathlib import Path

import pytest

from agentmemdb import __version__
from agentmemdb.cli import main


def test_check_reports_settings(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENTMEMDB_DB_PATH", str(tmp_path / "memory.db"))
    main(["--check"])
    info = json.loads(capsys.readouterr().out)
    assert info == {
        "version": __version__,
        "db_path": str(tmp_path / "memory.db"),
        "db_exists": False,
        "config_path": info["config_path"],
        "config_found": True,
        "auto_tags": 2,
    }


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"agentmemdb {__version__}"


def test_invalid_config_exits_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config.json"
    config.write_text("[]")
    monkeypatch.setenv("AGENTMEMDB_CONFIG", str(config))
    with pytest.raises(SystemExit) as exit_info:
        main(["--check"])
    assert exit_info.value.code == 2
    assert "must contain a JSON object" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("argv", "transport"), [([], "stdio"), (["--transport", "http", "--port", "9999"], "streamable-http")]
)
def test_runs_selected_transport(monkeypatch: pytest.MonkeyPatch, argv: list[str], transport: str) -> None:
    from agentmemdb.server import mcp

    calls = []
    monkeypatch.setattr(mcp, "run", lambda transport: calls.append(transport))
    monkeypatch.setattr(mcp.settings, "port", mcp.settings.port)
    main(argv)
    assert calls == [transport]
    if argv:
        assert mcp.settings.port == 9999
