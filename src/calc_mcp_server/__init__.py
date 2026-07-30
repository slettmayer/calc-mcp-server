"""Calculator MCP Server — exact arithmetic for LLMs.

A single ``calculate`` tool over a hand-rolled AST allowlist, so an agent can
do arithmetic without doing it mentally and without the server being a code
execution or denial-of-service surface.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("calc-mcp-server")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0+unknown"
