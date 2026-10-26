"""Packaging invariants."""

from importlib.metadata import version
from importlib.resources import files
from pathlib import Path

import agentmemdb

ROOT = Path(__file__).resolve().parent.parent


def test_version_matches_installed_metadata() -> None:
    assert version("agentmemdb") == agentmemdb.__version__


def test_packaged_icon_matches_logo() -> None:
    assert files("agentmemdb").joinpath("icon.svg").read_bytes() == (ROOT / "docs/assets/logo.svg").read_bytes()


def test_changelog_mentions_current_version() -> None:
    assert f"## [{agentmemdb.__version__}]" in (ROOT / "CHANGELOG.md").read_text()
