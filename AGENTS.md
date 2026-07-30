# Calculator MCP Server
> MCP server for exact arithmetic, usable by LLMs via the Model Context Protocol. One `calculate` tool over a hand-rolled AST allowlist — no `eval()`, no unbounded dependencies.

> **Editing this guide:** `AGENTS.md` is the single source of truth for project context, read by all AI
> coding agents and humans. Keep it concise — put detail in `docs/` and link it. When you change code that
> alters documented behavior, update the matching `docs/` file in the **same PR** (CodeRabbit enforces
> this — see [docs/README.md](docs/README.md)).

## Quick Reference
- **Lint**: `ruff check .`
- **Format**: `ruff format .`
- **Test**: `pytest tests/ -v`
- **Run server**: `uvx --from . calc-mcp-server` or `python -m calc_mcp_server.server`
- **Validate (CI)**: Ruff + pytest (all must pass via the `gate` job)
- **Release**: run the Auto Release workflow; the version comes from the git tag -- see [RELEASING.md](docs/tech/RELEASING.md)

## Where to Find Things
| I need to... | Read |
|--------------|------|
| Understand the architecture | [ARCHITECTURE.md](docs/tech/ARCHITECTURE.md) |
| Change the allowlist, a cap, or anything security-relevant | [SAFE-EVALUATION.md](docs/tech/SAFE-EVALUATION.md) |
| Write code that fits conventions | [CONVENTIONS.md](docs/tech/CONVENTIONS.md) |
| Know the tech stack | [TECH-STACK.md](docs/tech/TECH-STACK.md) |
| Write or run tests | [TESTING.md](docs/tech/TESTING.md) |
| Cut a release, or add a changelog entry | [RELEASING.md](docs/tech/RELEASING.md) |
| Understand the domain and why this repo exists | [OVERVIEW.md](docs/domain/OVERVIEW.md) |

## Architecture Overview
MCP presentation layer over a pure, dependency-free evaluator. Purely functional — no classes outside
the `MCPServer` instance and the exception hierarchy. All code lives in `src/calc_mcp_server/`.

- `server.py` -- MCPServer tool registration (1 tool), stdio entry point, turns `CalculatorError` into an `Error:` line
- `evaluator.py` -- parses, walks the AST against the allowlist, enforces the caps, renders the result
- `const.py` -- operator aliases, name/function allowlists, the four caps, float precision

Data flow: MCP tool call -> `server.py:calculate` -> `evaluator.evaluate()` (normalize aliases ->
`ast.parse` -> allowlist walk) -> `evaluator.format_result()` -> string.

See [Architecture](docs/tech/ARCHITECTURE.md) for module boundaries and data flow detail.

## Tech Stack
- Python 3.12+, `from __future__ import annotations` in every file
- `mcp[cli]` (`mcp.server.MCPServer`) for MCP server framework -- v2 line, pinned `>=2,<3`
- **Exactly one runtime dependency**, upper-bounded. This is the point of the repo -- see Structural Risks
- `ruff` for linting/formatting, `pytest` + `pytest-asyncio` for testing
- `uv` for environment management, `hatchling` + `hatch-vcs` build backend
- GitHub Actions CI (validate on push/PR)

See [Tech Stack](docs/tech/TECH-STACK.md) for full detail.

## Core Conventions
- Constants centralized in `const.py` -- no inline magic values, and the allowlists are written out rather than derived from `math`'s contents
- Logger: `_LOGGER = logging.getLogger(__name__)` with `%s` formatting (not f-strings)
- Import order: `__future__` -> stdlib -> third-party -> local
- `evaluator.py` raises typed `CalculatorError` subclasses; `server.py` catches them and returns a short `Error:` line -- the tool never raises
- Never coerce integers to float

See [Conventions](docs/tech/CONVENTIONS.md) for naming tables and full rules.

## Business Domain
A calculator MCP server for LLM voice agents, replacing the abandoned and broken
`mcp-server-calculator`. One tool, `calculate`, taking an expression string. Integer results are exact
at any size; floats render at 12 significant digits. Evaluation is guarded against both code execution
and resource exhaustion.

See [Domain Overview](docs/domain/OVERVIEW.md) for the tool contract, the supported expression surface,
and why this repo exists.

## Structural Risks
- **The server key `calculator` and the tool name `calculate` are load-bearing.** Home Assistant agent prompts route to `calculator__calculate` and an existing HA config entry points at `/servers/calculator/sse`. Renaming either breaks live voice agents -- see [OVERVIEW.md](docs/domain/OVERVIEW.md)
- **Never let a dependency go unbounded.** An unbounded `mcp>=1.4.1` in the package this replaces is what caused the outage this repo exists to prevent; `uv.lock` must be regenerated in the same commit as any `pyproject.toml` dependency change or `uv sync --locked` fails CI
- Widening `ALLOWED_FUNCTIONS` widens the attack surface -- any addition needs a cap review, since `factorial` needed one and `pow` needed another
- The caps in `const.py` are tuned to CPython's 4300-digit int-to-string limit; a runtime that changes that limit makes `MAX_RESULT_DIGITS` arbitrary rather than principled
- `MathError` wraps the stdlib's own message, whose wording differs between Python versions (3.12 says "math domain error", 3.14 says "expected a nonnegative input") -- tests assert the type, not the text
- Tool functions are called directly in tests, which relies on `@mcp.tool()` returning the function undecorated. That held across the v1 -> v2 migration; a future SDK returning a wrapper breaks the tests loudly rather than silently

## Detailed Guides
- [Technical Context](docs/tech/README.md) -- architecture, safe evaluation, tech stack, conventions, testing
- [Domain Context](docs/domain/README.md) -- tool contract, expression surface, why this exists
- [Documentation Guide](docs/README.md) -- how to maintain these docs
