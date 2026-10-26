"""End-to-end: the CLI and real MCP client sessions over stdio and HTTP."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import Implementation

from agentmemdb import __version__

SERVER = [sys.executable, "-m", "agentmemdb"]


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    return {**os.environ, "AGENTMEMDB_DB_PATH": str(tmp_path / "memory.db"), **extra}


def _text(result: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(result.content[0].text)
    return data


def test_check_prints_resolved_setup(tmp_path: Path) -> None:
    out = subprocess.run([*SERVER, "--check"], env=_env(tmp_path), capture_output=True, text=True, check=True)
    info = json.loads(out.stdout)
    assert info["version"] == __version__
    assert info["db_path"] == str(tmp_path / "memory.db")
    assert info["db_exists"] is False
    assert info["config_found"] is True
    assert info["auto_tags"] == 2


def test_version_flag() -> None:
    out = subprocess.run([*SERVER, "--version"], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == f"agentmemdb {__version__}"


def test_invalid_config_exits_with_message(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text('{"auto_tags": {"x": "("}}')
    out = subprocess.run(
        [*SERVER, "--check"], env=_env(tmp_path, AGENTMEMDB_CONFIG=str(config)), capture_output=True, text=True
    )
    assert out.returncode == 2
    assert out.stderr.startswith("agentmemdb: error: config file")


def test_stdio_session(tmp_path: Path) -> None:
    params = StdioServerParameters(command=SERVER[0], args=SERVER[1:], env=_env(tmp_path))

    async def run() -> tuple[Any, Any, dict[str, Any], dict[str, Any]]:
        client = Implementation(name="test-client", version="1.0")
        async with stdio_client(params) as (read, write), ClientSession(read, write, client_info=client) as session:
            init = await session.initialize()
            tools = await session.list_tools()
            saved = _text(await session.call_tool("save_memory", {"topic": "From stdio", "content": "c"}))
            memory = _text(await session.call_tool("get_memory", {"memory_id": saved["id"]}))
            stats = _text(await session.call_tool("get_stats", {}))
            return init, tools, memory, stats

    init, tools, memory, stats = asyncio.run(run())
    assert init.serverInfo.name == "agentmemdb"
    assert init.serverInfo.version == __version__
    assert init.serverInfo.icons[0].mimeType == "image/svg+xml"
    assert "Test policy: always save." in init.instructions
    assert len(tools.tools) == 16
    assert memory["source"] == "test-client"
    assert stats["db_path"] == str(tmp_path / "memory.db")
    assert stats["total_memories"] == 1


def test_http_session(tmp_path: Path) -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [*SERVER, "--transport", "http", "--port", str(port)],
        env=_env(tmp_path),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)

        async def run() -> tuple[Any, dict[str, Any]]:
            url = f"http://127.0.0.1:{port}/mcp"
            async with streamable_http_client(url) as (read, write, _), ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                return tools, _text(await session.call_tool("get_stats", {}))

        tools, stats = asyncio.run(run())
        assert len(tools.tools) == 16
        assert stats["db_path"] == str(tmp_path / "memory.db")
    finally:
        proc.terminate()
        proc.wait(timeout=5)
