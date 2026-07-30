# calc-mcp-server — design

**Date:** 2026-07-30 · **Source:** `CALCULATOR-MCP-HANDOVER.md`

## Problem

`mcp-server-calculator` (PyPI 0.2.0, abandoned since 2025-05-10) declares `mcp>=1.4.1` with no upper
bound. The MCP SDK's v2 release removed `mcp.server.fastmcp`, so `uvx …@latest` resolved 2.0.0 and the
import died — taking down the MCP Proxy add-on and all five servers in it.

No maintained Python replacement exists; every candidate carries the same unbounded `mcp` dependency.
The one maintained npm alternative computes in float64 and returns `121932631112635260` for
`123456789 * 987654321`, off by 9 — disqualifying for a tool that exists so the model does not
approximate.

## Decision

Own it. One tool, one bounded dependency, ~200 lines including the safety work.

### Evaluator: hand-rolled AST allowlist, not `simpleeval`

`simpleeval` is sound and would cut the implementation to ~15 lines, but it reintroduces exactly what
this repo exists to remove: an unbounded third-party dependency in the voice stack. It also only covers
part of the problem — its `MAX_POWER` handles the exponent bomb, but the factorial cap would still be
hand-rolled. Rejected alternatives (`ast.literal_eval`, restricted `eval()`, `asteval`, `sympy`) are
recorded in `docs/tech/SAFE-EVALUATION.md`.

Cost accepted: a subtle allowlist hole would be a code-execution bug rather than a wrong answer. Bounded
by the acceptance matrix and by keeping the walk a closed allowlist with a terminal `raise`.

## Architecture

Two layers, one direction. `evaluator.py` imports only `const.py` and the stdlib, so the
security-critical code is testable without the protocol layer.

```
server.py     -- MCP presentation, one tool, catches CalculatorError -> "Error: ..."
evaluator.py  -- normalize aliases -> ast.parse -> allowlist walk -> format
const.py      -- aliases, allowlists, caps
```

`evaluator.py` raises typed exceptions; `server.py` catches the base class. The tool never raises — a
rejected expression is an answer the agent reads back, not a tool-call failure.

## Safety

**Code execution.** Five node types handled (`Constant`, `Name`, `UnaryOp`, `BinOp`, `Call`), everything
else raises. `Attribute` is absent, blocking `(1).__class__.__bases__`. A `Call` is evaluated only when
its func is a bare `Name` in the allowlist, blocking `__import__('os').system(…)` before any argument is
evaluated.

**Resource exhaustion.** The half the incumbent misses — `9**9**9` hangs it for >5s.

| Cap | Value |
|---|---|
| Expression length | 500 chars |
| AST depth | 32 |
| Result digits | 4300 (CPython's int-to-string limit) |
| Factorial argument | 1000 |

The pow guard estimates `log10(|base|) * exponent` on the evaluated operands, not the exponent alone —
`(10**300)**300` has an exponent of 300 and a 90,000-digit result. The digit cap is re-checked at render
because multiplication can grow an integer without touching `**`.

## Output

Integers exact at any size. Floats collapsed to 12 significant digits, which removes IEEE-754 noise
(`0.1 + 0.2` → `0.3`) while keeping more precision than a calculator result is used at. Whole floats
keep `.0`, so `8 / 2` → `4.0` stays distinct from the exact integer `4`.

## Compatibility — load-bearing

Server key `calculator`, tool name `calculate`. Home Assistant agent prompts route to
`calculator__calculate` and an existing config entry points at `/servers/calculator/sse`. The PyPI
package name is independent, hence `calc-mcp-server`.

## Testing

- `test_evaluator.py` — the handover's acceptance matrix as two module-level tables, plus caps and
  rendering. The exponent-bomb test asserts wall-clock time, because "does not hang" is the requirement.
- `test_server.py` — the tool function called directly, which works because `@mcp.tool()` returns it
  undecorated (verified against the v2 migration in `geosphere-mcp-server`).
- `test_stdio.py` — real subprocess, real JSON-RPC. A unit-tested evaluator behind broken wiring is the
  exact failure that started this.

Stdlib `math` error wording changed between 3.12 and 3.14, so those tests assert the exception type
only, and `.python-version` pins local development to CI's 3.12.

## Out of scope

PyPI Trusted Publishing setup and the `GH_ACTION_APP_*` secrets cannot be created from this repo; the
first release is blocked on them. The `servers.json` swap on the live MCP Proxy host is likewise not a
repo change — it is an edit on the Home Assistant instance.
