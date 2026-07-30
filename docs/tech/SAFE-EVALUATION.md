# Safe Evaluation

> The threat model, the allowlist, and every resource cap. **Read this before touching `evaluator.py` or
> `const.py`** — both files exist to enforce what is described here, and a change that looks like a
> convenience is often a hole.

## Purpose
Documents how an untrusted expression string is evaluated without becoming a code-execution or
denial-of-service surface, and why each specific mechanism was chosen over the alternatives.

## Responsibilities
- The two-part threat model and what each part rules out
- The node, name and function allowlists
- Every resource cap, its value, and the reasoning behind that value
- The rejected alternatives, so they are not re-proposed

## Non-Responsibilities
- Module boundaries and data flow (see [ARCHITECTURE.md](ARCHITECTURE.md))
- The user-facing expression surface (see [OVERVIEW.md](../domain/OVERVIEW.md))
- Test structure (see [TESTING.md](TESTING.md))

## Threat model

Two problems. They are independent, and the package this server replaces only solved the first.

### 1. Code execution

The input is an arbitrary string from an LLM, which in turn may be relaying an arbitrary string from a
user. It must not be able to reach the interpreter.

`evaluate()` parses with `ast.parse(..., mode="eval")` and walks the tree in `_evaluate`, which handles
exactly five node types — `Constant`, `Name`, `UnaryOp`, `BinOp`, `Call` — and raises
`UnsupportedExpressionError` for everything else. The guarantee comes from the walk being an allowlist
with a terminal `raise`, not from enumerating things to block.

Two consequences carry most of the weight:

- **`Attribute` is not handled**, so `(1).__class__.__bases__` is rejected at the outermost node. This
  is what blocks the classic sandbox escape, which works by walking from any object up to
  `object.__subclasses__()` and down to something that can open a file or spawn a process.
- **A `Call` is only evaluated when `node.func` is a bare `Name` in `ALLOWED_FUNCTIONS`.** So
  `__import__('os').system(...)` is rejected before a single argument is evaluated: its func is an
  `Attribute`, not a name. A call on the result of another call is rejected for the same reason.

Two smaller ones:

- **`Constant` accepts only `int` and `float`.** Strings never enter evaluation, so no allowlisted
  function can be handed one. `bool` is excluded explicitly because it is a subclass of `int` and
  `True + 1` would otherwise quietly evaluate to `2`.
- **Keyword arguments are rejected**, since no allowlisted function needs them and they widen the call
  surface for nothing.

### 2. Resource exhaustion

An allowlist alone still lets an expression consume the process. This is the half the incumbent misses:
`9**9**9` hangs it for over five seconds, and `factorial(200000)` only errors by the accident of
CPython's int-to-string limit — long after the CPU time has been spent.

Since this server runs behind a shared MCP proxy, a hang is not a slow answer. It is an outage for every
other server in the same process.

## The caps

Four caps and one precision constant live in `const.py`. Every **cap** rejects rather than truncates, and
is checked before the expensive work wherever that is possible. `MAX_RESULT_DIGITS` is the one that cannot
be: it is enforced before exponentiating *and* again at render, because multiplication can grow an integer
past it without ever touching `**` — see [below](#why-the-digit-cap-is-also-enforced-at-render).

`RESULT_PRECISION` is not a cap: it is rendering precision, applied unconditionally to every float result
and rejecting nothing. It is listed here because it shares the file and is easy to mistake for a bound.

| Cap | Value | Where | Why this value |
|---|---|---|---|
| `MAX_EXPRESSION_LENGTH` | 500 chars | `evaluate()`, before parsing | A cheap first gate, so a pathological input never gets an AST built for it |
| `MAX_AST_DEPTH` | 32 | `_evaluate()`, per level | Bounds the walk's recursion. Far deeper than anything a person types — redundant parentheses produce no nodes, so `((((1))))` is 1 level |
| `MAX_RESULT_DIGITS` | 4300 | `_guarded_pow()`, `format_result()` | CPython's default int-to-string limit. A larger result could not be rendered anyway, so the line is principled, not arbitrary |
| `MAX_FACTORIAL_ARG` | 1000 | `_evaluate_call()` | 1000! has 2568 digits and computes in well under a millisecond. 2000! has 5736 and so exceeds `MAX_RESULT_DIGITS` regardless |
| `RESULT_PRECISION` | 12 sig. digits | `format_result()` | Not a safety cap. IEEE-754 noise appears near the 16th digit, so 12 hides it while keeping more precision than a result is read at |

### Why the exponent cap is on the estimated result, not the exponent

The obvious guard — reject when the exponent exceeds some constant — is not sufficient.
`(10**300)**300` has an exponent of just 300 and a 90,000-digit result.

`_guarded_pow` instead estimates the result's size from both already-evaluated operands, as
`log10(|base|) * exponent`, and rejects before calling `operator.pow`. That single rule covers both
shapes: `9**9**9` evaluates its right-associative inner `9**9` to 387,420,489 cheaply, then fails on the
outer power because the estimate is ~370 million digits.

The guard is skipped when `|base| <= 1` or the exponent is negative, where the result shrinks rather
than grows. A float that overflows there is caught as `OverflowError` and re-raised as
`LimitExceededError`.

### Why the digit cap is also enforced at render

Exponentiation is not the only way to grow an integer. `factorial(1000) * factorial(1000)` passes every
cap above and produces ~5135 digits, and `str()` on it raises. So `format_result` re-checks, sizing via
`value.bit_length() * log10(2)` rather than `len(str(value))` — calling `str()` to find out whether
`str()` is safe would defeat the purpose.

## Rejected alternatives

Do not re-propose these; each was evaluated and ruled out.

| Approach | Why not |
|---|---|
| `ast.literal_eval` | Not an expression evaluator. Literals and containers only — it cannot do `2 + 2` |
| `eval()` with restricted globals | Escapable via `().__class__.__bases__` chains. There is no safe version of this |
| `simpleeval` | Sound, but reintroduces an unbounded third-party dependency — see below |
| `asteval` | Supports statements and assignments. Much broader attack surface for no gain |
| `sympy` | Multi-megabyte, and `sympify` has historically leaned on `eval` |

`simpleeval` is the closest call, so it is worth being explicit about. It is purpose-built and sound, but
it reintroduces exactly the thing this repo exists to remove: an unbounded third-party dependency in the
voice stack. It also covers only part of the problem — its `MAX_POWER` handles the exponent bomb, but the
factorial cap would still be hand-rolled here.

## Known Risks
- The allowlists are the security boundary. Adding to `ALLOWED_FUNCTIONS` needs a cap review — two of
  the entries there (`factorial`, and `pow` via `**`) each needed one.
- The 4300-digit figure is CPython-specific. On a runtime with a different int-to-string limit,
  `MAX_RESULT_DIGITS` stops being principled and becomes arbitrary.
- Wall-clock time is bounded indirectly, through result size. An expression that is slow without being
  large — a long chain of transcendental calls — is not covered. In practice `MAX_EXPRESSION_LENGTH`
  bounds it, but there is no explicit timeout.

## Extension Guidelines
- Adding a function: put it in `ALLOWED_FUNCTIONS` in `const.py`, and ask whether its cost grows
  super-linearly in its argument. If it does, it needs a cap alongside `MAX_FACTORIAL_ARG`.
- Adding an operator: add it to `_BINARY_OPS` or `_UNARY_OPS`, and ask whether it can grow a result.
- Never add `Attribute` or `Subscript` to the walk. There is no calculator feature that needs either.
- Every change here needs a row in `ACCEPTANCE_REJECTED` or `ACCEPTANCE_VALID` in
  `tests/test_evaluator.py`.
