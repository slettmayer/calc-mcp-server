"""Tests for the MCP tool function in server.py.

The tool function is called directly, which works because `@mcp.tool()`
registers the function and returns it undecorated rather than wrapping it.
That held across the v1 -> v2 SDK migration; if a future SDK returns a wrapper
these tests fail loudly rather than silently testing nothing.
"""

from __future__ import annotations

import pytest

from calc_mcp_server.server import calculate


@pytest.mark.asyncio
async def test_calculate_returns_the_result() -> None:
    assert await calculate("2 + 3 * (4 - 1) / 2 ** 2") == "4.25"


@pytest.mark.asyncio
async def test_calculate_returns_exact_integers() -> None:
    assert await calculate("123456789 * 987654321") == "121932631112635269"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("expression", "fragment"),
    [
        ("__import__('os').system('echo pwned')", "unsupported expression: Call"),
        ("(1).__class__.__bases__", "unsupported expression: Attribute"),
        ("9**9**9", "exponent too large"),
        ("factorial(200000)", "argument too large"),
        ("1/0", "division by zero"),
        ("2 +", "could not parse"),
    ],
)
async def test_calculate_returns_an_error_line_instead_of_raising(
    expression: str, fragment: str
) -> None:
    """The tool never raises — a rejected expression is an answer, not a failure."""
    result = await calculate(expression)
    assert result.startswith("Error: ")
    assert fragment in result
