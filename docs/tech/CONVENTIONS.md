# Conventions

## Purpose
Documents naming, code style, error handling, and import patterns.

## Responsibilities
- Naming rules for modules, functions, constants and exceptions
- Import ordering and style
- The error-handling contract between layers
- Docstring and comment expectations
- Where `scripts/` release tooling deliberately diverges from the `src/` rules

## Non-Responsibilities
- Module boundaries (see [ARCHITECTURE.md](ARCHITECTURE.md))
- Test naming (see [TESTING.md](TESTING.md))

## Overview

### Naming

| Kind | Rule | Examples |
|---|---|---|
| Module | lowercase, single word where possible | `evaluator.py`, `const.py`, `server.py` |
| Public function | `snake_case`, verb-first | `evaluate`, `format_result` |
| Private function | leading underscore | `_evaluate`, `_evaluate_call`, `_guarded_pow` |
| MCP tool | plain verb, no prefix | `calculate` |
| Constant | `UPPER_SNAKE_CASE` in `const.py` | `MAX_AST_DEPTH`, `ALLOWED_FUNCTIONS` |
| Module-private constant | leading underscore, defined where used | `_BINARY_OPS`, `_LOG10_2` |
| Exception | `*Error`, subclassing `CalculatorError` | `LimitExceededError` |

Caps are named `MAX_*` and carry their unit in the docstring or comment, not the name.

### Style
- `from __future__ import annotations` at the top of every file
- Import order: `__future__` → stdlib → third-party → local, each group separated by a blank line
  (enforced by ruff's `I` rules)
- Line length 88, ruff-formatted
- Type annotations on every function signature, including `-> None`
- `Number = int | float` is the shared alias for a result; do not write `float` where an int can occur

### Constants
- Everything tunable lives in `const.py`. No inline magic values.
- The allowlists are written out explicitly rather than derived from `math`'s contents. Deriving them
  would silently widen the attack surface with each Python release; written out, a widening shows in a
  diff. See [SAFE-EVALUATION.md](SAFE-EVALUATION.md).

### Error handling

The contract, in one sentence: **`evaluator.py` raises, `server.py` catches, the tool never raises.**

This applies to `src/`. `scripts/` is release tooling and deliberately follows a different contract — see
[Release tooling](#release-tooling) below.

- Every exception `evaluate()` can provoke is translated into a `CalculatorError` subclass. Bare stdlib
  exceptions must not escape it.
- Exception messages are lowercase, complete sentences without a trailing period, and describe what was
  wrong with the *expression* — they are read aloud by a voice agent. `"exponent too large: the result
  would have about 370000000 digits, over the limit of 4300"`, not `"OverflowError"`.
- Where a message comes from the stdlib (`MathError` wrapping a `ValueError`), it is passed through
  unchanged. Its wording varies by Python version, so tests assert the exception type, not the text.
- `server.py` catches the `CalculatorError` base only. Catching a subclass individually would let a new
  subclass escape as a tool-call failure.

### Logging
- `_LOGGER = logging.getLogger(__name__)` at module level
- `%s` lazy formatting, never f-strings: `_LOGGER.info("rejected expression %r: %s", expression, err)`
- Rejected expressions log at `info`. Nothing logs at `error` — a rejected expression is a normal
  outcome, not a fault.

### Docstrings and comments
- Every module, class and function has a docstring.
- Comments explain **why**, not what. The reasoning behind a cap's value, or why an alternative was
  rejected, belongs in the code near the decision — and in
  [SAFE-EVALUATION.md](SAFE-EVALUATION.md) at length.
- The `calculate` tool docstring is the tool description the LLM sees. Keep it tight and concrete: it is
  how the agent decides whether to reach for the calculator at all.

### Release tooling

`scripts/changelog_release.py` ships outside the package and is a command-line tool, not part of the
server. It keeps the shared style rules — `from __future__ import annotations`, import order, full
annotations, ruff formatting — but departs on error handling, deliberately:

| Rule in `src/` | In `scripts/` | Why |
|---|---|---|
| `_LOGGER` with `%s` formatting | `print(f"error: {err}", file=sys.stderr)` | A CLI's output *is* its interface; a workflow log reads stderr, not a logging config |
| Raise `CalculatorError` subclasses | Raise `ChangelogError(Exception)` | A different domain. Subclassing `CalculatorError` would let `server.py` swallow a release failure as an `Error:` line |
| Exceptions propagate to the caller | `main()` catches and returns exit code `1` | The workflow step's pass/fail signal is the process exit code |

Do not "fix" `scripts/` to match `src/`. See [RELEASING.md](RELEASING.md) for what the script does.

## Known Risks
- The "never coerce to float" rule is not enforced by anything except review and
  `test_evaluate_preserves_integer_exactness`. A helper that calls `float()` on a result would pass
  every other test.

## Extension Guidelines
- Follow the existing module's patterns rather than introducing a new style.
- A new exception type subclasses `CalculatorError`, or `server.py` will not catch it.
- A new constant goes in `const.py` unless it is only meaningful inside one module, in which case it is
  underscore-prefixed and defined next to its use.
