"""End-to-end smoke test over the real stdio transport.

A unit-tested evaluator behind broken MCP wiring is exactly the failure that
motivated this server: the package it replaces passed its own tests while
failing to import under the v2 SDK. These tests spawn the actual entry point
and speak JSON-RPC to it, so a wiring break cannot pass CI.

Nothing external is contacted, so this runs in the default suite rather than
behind an `integration` marker.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

import pytest

PROTOCOL_VERSION = "2025-06-18"
TIMEOUT_S = 60


def _request(request_id: int, method: str, params: dict[str, Any]) -> str:
    return json.dumps(
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    )


def _notification(method: str) -> str:
    return json.dumps({"jsonrpc": "2.0", "method": method})


def _run_session(*requests: str) -> list[dict[str, Any]]:
    """Run a full stdio session against the server and return its responses.

    Every session opens with the initialize handshake, so callers only pass the
    requests they actually care about.

    Each request is written and its response read back before the next is sent,
    rather than piping the whole script in at once. Closing stdin cancels the
    session's task group, which discards any tool call still in flight — so a
    write-everything-then-read approach only ever sees the initialize response.
    """
    process = subprocess.Popen(
        [sys.executable, "-m", "calc_mcp_server.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stdin is not None and process.stdout is not None

    def exchange(line: str) -> dict[str, Any]:
        process.stdin.write(line + "\n")
        process.stdin.flush()
        response = process.stdout.readline()
        if not response.strip():
            process.kill()
            stderr = process.communicate(timeout=TIMEOUT_S)[1]
            pytest.fail(f"no response to {line}; stderr:\n{stderr}")
        return json.loads(response)

    try:
        responses = [
            exchange(
                _request(
                    1,
                    "initialize",
                    {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0"},
                    },
                )
            )
        ]
        process.stdin.write(_notification("notifications/initialized") + "\n")
        process.stdin.flush()
        responses.extend(exchange(request) for request in requests)
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            process.kill()

    return responses


def _by_id(responses: list[dict[str, Any]], request_id: int) -> dict[str, Any]:
    for response in responses:
        if response.get("id") == request_id:
            return response
    pytest.fail(f"no response with id {request_id} in {responses}")


def _tool_text(response: dict[str, Any]) -> str:
    return response["result"]["content"][0]["text"]


def test_initialize_advertises_the_server_name_and_version() -> None:
    info = _by_id(_run_session(), 1)["result"]["serverInfo"]
    assert info["name"] == "calculator"
    # v1 reported the SDK's version here; v2 reports whatever is passed in.
    assert info["version"] not in ("", None)


def test_tools_list_exposes_exactly_the_calculate_tool() -> None:
    """The name is load-bearing: HA prompts route to `calculator__calculate`."""
    responses = _run_session(_request(2, "tools/list", {}))
    tools = _by_id(responses, 2)["result"]["tools"]
    assert [tool["name"] for tool in tools] == ["calculate"]
    assert "expression" in tools[0]["inputSchema"]["properties"]


def test_calling_calculate_over_stdio_returns_the_result() -> None:
    responses = _run_session(
        _request(
            2,
            "tools/call",
            {"name": "calculate", "arguments": {"expression": "123456789 * 987654321"}},
        )
    )
    assert _tool_text(_by_id(responses, 2)) == "121932631112635269"


def test_calling_calculate_with_a_rejected_expression_is_not_a_protocol_error() -> None:
    responses = _run_session(
        _request(
            2,
            "tools/call",
            {"name": "calculate", "arguments": {"expression": "9**9**9"}},
        )
    )
    response = _by_id(responses, 2)
    assert "error" not in response
    assert "exponent too large" in _tool_text(response)
