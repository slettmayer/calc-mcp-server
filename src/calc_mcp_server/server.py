"""MCP server exposing a single safe arithmetic tool.

The server key is ``calculator`` and the tool is ``calculate`` because Home
Assistant agent prompts already route to ``calculator__calculate``. Renaming
either breaks those prompts and the existing HA config entry — see
[OVERVIEW.md](../../docs/domain/OVERVIEW.md).

The tool never raises: every rejected expression resolves to a short ``Error:``
line, so a malformed calculation is an answer the agent can read back rather
than a tool-call failure.
"""

from __future__ import annotations

import logging

from mcp.server import MCPServer

from calc_mcp_server import __version__
from calc_mcp_server.evaluator import CalculatorError, evaluate, format_result

_LOGGER = logging.getLogger(__name__)

mcp = MCPServer(
    "calculator",
    # v2 advertises this verbatim and defaults it to "" (v1 had no such
    # parameter and reported the SDK's own version instead).
    version=__version__,
    instructions=(
        "Exact arithmetic. Use this rather than computing mentally for anything "
        "beyond a trivial single-digit sum — integer results stay exact at any "
        "size instead of being rounded to floating point. Supports + - * / // % "
        "and ** (or ^), parentheses, the constants pi, e and tau, and common "
        "functions including sqrt, log, the trigonometric family and factorial."
    ),
)


@mcp.tool()
async def calculate(expression: str) -> str:
    """Evaluate an arithmetic expression and return the result.

    Args:
        expression: The expression to evaluate, for example "2 + 3 * (4 - 1)",
            "sqrt(16) + sin(pi/2)" or "123456789 * 987654321". `^` is accepted
            as a power operator, and `×` and `÷` as multiply and divide.
    """
    try:
        return format_result(evaluate(expression))
    except CalculatorError as err:
        _LOGGER.info("rejected expression %r: %s", expression, err)
        return f"Error: {err}"


def main() -> None:
    """Run the calculator MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
