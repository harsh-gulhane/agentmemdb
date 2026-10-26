"""Command-line entry point: run the server over stdio or HTTP, or print the resolved setup."""

import argparse
import json
import os
from collections.abc import Sequence

from agentmemdb import __version__
from agentmemdb.config import ConfigError, load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentmemdb", description="Local-first, shared long-term memory for AI agents (MCP server)"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="stdio (default, one process per client) or streamable HTTP on 127.0.0.1",
    )
    parser.add_argument("--port", type=int, default=8765, help="HTTP port (default: 8765); endpoint is /mcp")
    parser.add_argument("--check", action="store_true", help="print the resolved database and config paths, then exit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
    except ConfigError as err:
        parser.exit(2, f"agentmemdb: error: {err}\n")

    if args.check:
        info = {
            "version": __version__,
            "db_path": settings.db_path,
            "db_exists": os.path.exists(settings.db_path),
            "config_path": settings.config_path,
            "config_found": settings.config_found,
            "auto_tags": len(settings.auto_tags),
        }
        print(json.dumps(info, indent=2))
        return

    from agentmemdb.server import mcp

    if args.transport == "http":
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
