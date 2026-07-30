# Architecture

## Purpose
Documents the project structure, module boundaries, layering, and data flow.

## Responsibilities
- Defining the module layout and what each module owns
- Describing the request path from MCP tool call to returned string
- Documenting the error-handling boundary between layers

## Non-Responsibilities
- The safe-evaluation threat model and caps (see [SAFE-EVALUATION.md](SAFE-EVALUATION.md))
- Code style and naming (see [CONVENTIONS.md](CONVENTIONS.md))
- Test structure (see [TESTING.md](TESTING.md))

## Overview

### Layout
```
src/calc_mcp_server/
  __init__.py     -- package docstring, __version__ from installed metadata
  const.py        -- operator aliases, allowlists, caps, float precision
  evaluator.py    -- pure evaluation: parse, walk, enforce caps, render
  server.py       -- MCP presentation layer: one tool, stdio entry point
  py.typed        -- PEP 561 marker
scripts/
  changelog_release.py  -- release tooling, not part of the shipped package
```

### Layering

Two layers, one direction. `evaluator.py` imports only `const.py` and the standard library — it has no
knowledge of MCP and is fully testable without it. `server.py` imports `evaluator` and the SDK.

```
server.py      -- MCP presentation
    |
evaluator.py   -- pure logic (no MCP, no third-party imports)
    |
const.py       -- data only
```

Nothing imports `server.py` except the entry point and the tests.

### Data flow

```
MCP tool call
  -> server.py:calculate(expression)
  -> evaluator.evaluate(expression)
       -> length gate
       -> operator alias substitution (^ -> **, × -> *, ÷ -> /, − -> -)
       -> ast.parse(mode="eval")
       -> _evaluate() walks the tree against the allowlist, enforcing depth
          and the pow/factorial caps as it goes
  -> evaluator.format_result(value)
       -> int: digit-size check, then exact rendering
       -> float: collapse to 12 significant digits
  -> str returned to the caller
```

The alias substitution happens on the raw string **before** parsing, because `^` is a valid Python
operator (bitwise XOR) and would otherwise parse successfully into the wrong operation.

### Error handling boundary

`evaluator.py` raises; `server.py` catches. This is the same split the sibling servers use.

- `evaluator.py` raises `CalculatorError` subclasses — `ExpressionSyntaxError`,
  `UnsupportedExpressionError`, `LimitExceededError`, `MathError` — and translates every stdlib
  exception it can provoke (`ZeroDivisionError`, `ValueError`, `TypeError`, `OverflowError`,
  `RecursionError`) into one of them. Nothing else escapes `evaluate()`.
- `server.py` catches the `CalculatorError` base and returns `f"Error: {err}"`. **The tool never
  raises.** A rejected expression is an answer the agent can read back to the user, not a tool-call
  failure it has to recover from.

`format_result` can also raise `LimitExceededError`, which is why the `try` in `server.py:calculate`
wraps both calls rather than just `evaluate`.

## Dependencies
- `mcp[cli]` — used only in `server.py`
- Standard library only elsewhere (`ast`, `math`, `operator`, `logging`)

## Design Decisions
- **Evaluator has no MCP dependency**: the security-critical code is testable and reviewable without the
  protocol layer, and an SDK change cannot alter evaluation behavior.
- **One tool, not a suite**: the name `calculate` is load-bearing for existing Home Assistant prompts
  (see [OVERVIEW.md](../domain/OVERVIEW.md)), and a wider surface would mean more to keep safe.
- **Allowlists in `const.py`, not derived from `math`**: `dir(math)` would silently widen the attack
  surface whenever Python adds a function. Written out, any widening appears in a diff.
- **Formatting lives in `evaluator.py`, not a separate module**: `format_result` enforces the integer
  digit cap and the int/float distinction, so it is part of the numeric contract rather than
  presentation. The sibling servers' `format.py` renders markdown, which this server does not do.

## Known Risks
- `format_result` raising means result rendering is a second failure point, easy to miss when adding a
  caller. Any new call site must be inside the `CalculatorError` handler.
- The allowlist walk is recursive. `MAX_AST_DEPTH` bounds it, but `RecursionError` is still caught as a
  backstop in case the two ever disagree.

## Extension Guidelines
- New evaluation behavior goes in `evaluator.py` and needs a `docs/tech/SAFE-EVALUATION.md` update in
  the same PR.
- New constants go in `const.py`. No inline magic values.
- Adding a second tool would mean revisiting the compatibility constraints in
  [OVERVIEW.md](../domain/OVERVIEW.md) first.
