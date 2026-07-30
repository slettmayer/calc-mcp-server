# Testing

## Purpose
Documents the test structure, patterns, tooling, and conventions used in the project.

## Responsibilities
- Defining test file organization and naming
- Documenting the acceptance matrix and where new cases go
- Explaining the stdio round-trip harness
- Listing test commands

## Non-Responsibilities
- Code style rules (see [CONVENTIONS.md](CONVENTIONS.md))
- Architecture and module boundaries (see [ARCHITECTURE.md](ARCHITECTURE.md))
- What the caps are and why (see [SAFE-EVALUATION.md](SAFE-EVALUATION.md))

## Overview

### Test Structure
```
tests/
  conftest.py               -- puts `scripts/` on sys.path so release tooling is importable
  test_evaluator.py         -- the acceptance matrix, the caps, result rendering
  test_server.py            -- the MCP tool function, called directly
  test_stdio.py             -- end-to-end round trip over the real stdio transport
  test_server_json.py       -- `server.json` against the MCP Registry's constraints
  test_changelog_release.py -- release tooling, git faked
```

Everything runs in CI. There is no `integration` marker, because nothing external is contacted.

`conftest.py` exists only so `test_changelog_release.py` can import `scripts/changelog_release.py`, which
ships outside the package and is therefore not importable by default.

### The acceptance matrix

`test_evaluator.py` opens with two module-level tables:

- `ACCEPTANCE_VALID` — `(expression, rendered result)` pairs
- `ACCEPTANCE_REJECTED` — `(expression, exception type, message fragment)` triples

Each row is either behavior the abandoned `mcp-server-calculator` got right and must not regress, or
behavior it got wrong and this server exists to fix. **Any change to the allowlist or a cap adds a row
here.** That is the single most useful review signal in the repo.

Message fragments are matched with `pytest.raises(match=...)`, so they are regexes — keep them plain.

### Test Method Naming
- Pattern: `test_<subject>_<expected behavior>()` with a `-> None` return annotation
- Examples: `test_exponent_bomb_is_rejected_quickly`, `test_format_result_hides_float_noise`,
  `test_calculate_returns_an_error_line_instead_of_raising`
- Tests are grouped by concern with `# --- Section header ---` comment banners

### What the caps tests assert

Cap tests assert the *reason* the cap exists, not just that an exception appears:

- `test_exponent_bomb_is_rejected_quickly` asserts wall-clock time, because "raises" is not the
  requirement — "does not hang" is. The incumbent takes over five seconds on `9**9**9`.
- `test_large_base_with_small_exponent_is_rejected` covers `(10**300)**300`, which a naive
  exponent-only cap would let through.
- `test_multiplication_past_the_digit_cap_is_rejected_at_render` covers growth that never touches `**`.

### Testing the tool function

`test_server.py` imports `calculate` from `server.py` and calls it directly. This works because
`@mcp.tool()` registers the function and returns it undecorated rather than wrapping it — true in SDK
v1 and still true in v2.

If a future SDK returns a `Tool` wrapper, these tests fail at the call, loudly. That is intended: the
alternative is tests that silently exercise a wrapper instead of the tool.

The same file also guards the *advertised* surface:
`test_docstring_advertises_every_operator_alias` asserts every key of `OPERATOR_ALIASES` appears in the
`calculate` docstring. An alias the evaluator accepts but the description omits is a capability no agent
will ever send — which is what happened to `·` and `−`. Constants and functions have no equivalent guard
yet and remain review-only.

### The stdio round trip

`test_stdio.py` spawns `python -m calc_mcp_server.server` as a subprocess and speaks JSON-RPC to it over
real pipes: initialize, `tools/list`, `tools/call`.

This exists because a unit-tested evaluator behind broken MCP wiring is precisely the failure that
motivated the repo — the package this replaces passed its own tests while failing to import.

**The harness writes one request and reads its response before sending the next.** Piping the whole
script in at once does not work: closing stdin cancels the session's task group and discards any tool
call still in flight, so only the initialize response ever comes back. If these tests start returning
"no response with id 2", that is the cause.

### Validating the registry manifest

`test_server_json.py` checks `server.json` against constraints the MCP Registry only enforces at publish
time — which is *after* the PyPI upload has succeeded and the tag is immovable, so a rejection there
cannot be fixed by re-running the job. It costs a whole version number.

That is not hypothetical: `v0.1.0` reached PyPI and then failed the registry with
`expected length <= 100` on a 116-character description. The tests cover the description limit, the
package identifier matching `pyproject.toml`'s distribution name, the owned `io.github.slettmayer`
namespace, the `mcp-name` ownership marker in the README, and the two version fields agreeing.

Neither the referenced JSON schema nor anything else in the toolchain catches these, so the suite is the
only pre-release gate. See [RELEASING.md](RELEASING.md) for how the versions get rewritten from the tag.

### Async Testing
- `pytest-asyncio` with `asyncio_mode = "auto"` in `pyproject.toml`
- Tests still carry explicit `@pytest.mark.asyncio` decorators for clarity

### Assertions
- Plain `assert` statements, no helper methods
- Rejection paths assert the expected typed exception via `pytest.raises`
- Where a message originates in the stdlib (`sqrt(-1)`, `log(0)`, `factorial(2.5)`), only the exception
  **type** is asserted. The wording changed between Python 3.12 and 3.14, and pinning it makes the suite
  interpreter-specific.

### Commands
| Command | Scope | Runs in CI |
|---|---|---|
| `uv run pytest tests/ -v` | Everything | Yes |
| `uv run pytest tests/test_evaluator.py -v` | Evaluator and caps only | — |
| `uv run ruff check .` | Lint | Yes |
| `uv run ruff format . --check` | Format | Yes |

## Dependencies
- `pytest` — test runner
- `pytest-asyncio` — async test support
- `subprocess` (stdlib) — the stdio harness

No mocking library is needed: the evaluator is pure, and the stdio tests use the real thing.

## Known Risks
- `test_exponent_bomb_is_rejected_quickly` asserts a wall-clock bound. The margin is ~1000x, but a
  severely overloaded runner could in principle flake it.
- The stdio tests spawn a real interpreter, so they are the slowest in the suite and the ones most
  likely to be affected by an environment problem rather than a code problem.

## Extension Guidelines
- New allowlist entry or cap change → add a row to `ACCEPTANCE_VALID` or `ACCEPTANCE_REJECTED`.
- New rendering behavior → add to the "Result rendering" section of `test_evaluator.py`.
- New tool or changed tool signature → add to `test_stdio.py`, not just `test_server.py`. The protocol
  surface is what consumers actually see.
- Editing `server.json`, the README's `mcp-name` marker, or the distribution name → run
  `uv run pytest tests/test_server_json.py` before merging. A registry constraint that is only discovered
  at publish time burns a version number.
