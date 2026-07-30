# Domain Overview

## Purpose
Documents what this server is for, the tool contract, the supported expression surface, and the
compatibility constraints that are load-bearing for the Home Assistant voice stack.

## Responsibilities
- Why this server exists rather than an off-the-shelf one
- The `calculate` tool contract and its output format
- The full supported expression surface
- The naming constraints that must not change
- Glossary

## Non-Responsibilities
- How safety is implemented (see [SAFE-EVALUATION.md](../tech/SAFE-EVALUATION.md))
- Module structure (see [ARCHITECTURE.md](../tech/ARCHITECTURE.md))

## Domain classification

A single-purpose arithmetic gateway for LLM agents. No state, no I/O, no external API. The entire domain
is: *a string comes in, a number goes out, and neither the process nor the host is at risk in between.*

The consumer is a Home Assistant voice agent that is instructed never to do arithmetic mentally.

## Why this server exists

The widely-used `mcp-server-calculator` (PyPI 0.2.0, last commit 2025-05-10) declared `mcp>=1.4.1` with
no upper bound. When the MCP Python SDK released v2 and removed `mcp.server.fastmcp`, `uvx …@latest`
resolved 2.0.0 and the import died — taking down the entire MCP Proxy add-on and all five servers
running in it.

No maintained Python replacement exists. Every Python candidate surveyed carried the same unbounded
`mcp` dependency and so the same failure mode. The one actively-maintained alternative
(`@cyanheads/calculator-mcp-server`, npm) computes in float64, so `123456789 * 987654321` returns
`121932631112635260` — off by 9. That is a disqualifying trait in a tool whose entire purpose is that
the model should not be approximating.

So the server is owned here, at roughly 200 lines including the safety work, with one bounded
dependency.

## Compatibility constraints — do not change these

The Home Assistant side already references this tool by name. Changing either name means editing agent
prompts and re-creating a config entry on the live instance.

| Constraint | Value | Referenced by |
|---|---|---|
| MCP server key | `calculator` | `ai_agents.yaml:299` config entry `mcp-01KJT2Z7D2DZP4PA8B1MTNGY28`, pointing at `/servers/calculator/sse` |
| Tool name | `calculate` | `ai_agents.yaml:140` instructs agents to use `calculator__calculate` |

Together these form the `calculator__calculate` identifier the agent prompts route to. The **PyPI
package name is independent** of both, which is why it can be `calc-mcp-server` while the server key
stays `calculator`.

Softer references, kept consistent but not load-bearing: `ai_agents.yaml:88` ("use the calculator tool")
and `packages/voice.yaml:684` ("calculate the sum using the Calculator tool").

## The `calculate` tool

| Argument | Type | Required | Description |
|---|---|---|---|
| `expression` | `str` | yes | The arithmetic expression to evaluate |

Returns a string: either the result, or a line beginning with `Error: ` explaining the rejection. **The
tool never raises**, so a malformed expression is an answer the agent can read back to the user rather
than a tool-call failure it has to recover from.

### Expression surface

**Operators** — `+` `-` `*` `/` `//` `%` `**`, parentheses, unary `+` and `-`.

**Aliases**, substituted before parsing — `^` → `**`, `×` → `*`, `·` → `*`, `÷` → `/`, `−` (U+2212) →
`-`. The Unicode forms are what a speech-to-text layer produces; `^` is what every calculator UI uses
for a power, though Python reads it as bitwise XOR.

**Constants** — `pi`, `e`, `tau`. `inf` and `nan` are deliberately absent: neither is a useful answer to
a spoken question, and both propagate silently through the rest of an expression.

**Functions** — `abs` `round` `min` `max` `sqrt` `exp` `log` `log2` `log10` `sin` `cos` `tan` `asin`
`acos` `atan` `atan2` `degrees` `radians` `hypot` `floor` `ceil` `factorial` `gcd` `lcm`.

### Output contract

| Input shape | Output | Rationale |
|---|---|---|
| Integer arithmetic | Exact integer of any size, up to 4300 digits | `123456789 * 987654321` → `121932631112635269`, not a rounded float |
| Float arithmetic | 12 significant digits | `0.1 + 0.2` → `0.3`, not `0.30000000000000004` |
| Whole float | Keeps `.0` | `8 / 2` → `4.0`, visibly distinct from the exact integer `4` |
| Rejected | `Error: <reason>` | Read aloud by a voice agent, so the reason is plain English |

The int/float distinction is preserved deliberately. `4` and `4.0` mean different things here: the first
is exact, the second is the result of a division that happened to come out whole.

## Glossary

| Term | Meaning |
|---|---|
| **Allowlist** | The explicit set of AST node types, names and functions that may be evaluated. Everything else is rejected — the guarantee comes from the list being closed, not from blocking known-bad input |
| **Cap** | A resource bound (length, depth, result size, factorial argument) enforced before the expensive work happens |
| **Exponent bomb** | An expression like `9**9**9` that is trivially short but occupies the process for minutes on bignum exponentiation |
| **Exactness** | Integer results are never coerced to float. The property that distinguishes this server from the float64 alternatives |
| **MCP Proxy** | The Home Assistant add-on hosting several MCP servers in one process — which is why a hang here is an outage for unrelated servers |

## Known Risks
- The `calculator` / `calculate` names are referenced from a live Home Assistant instance, not from any
  file in this repo. Nothing here will fail if they change; the voice agents will.
- The expression surface is what agents discover through the tool docstring. Widening it without
  updating that docstring means the capability exists but is never used.

## Extension Guidelines
- Adding a function or constant: update `ALLOWED_FUNCTIONS` / `ALLOWED_CONSTANTS` in `const.py`, the
  surface list above, the README, and the tool docstring — and review it against
  [SAFE-EVALUATION.md](../tech/SAFE-EVALUATION.md).
- Adding a second tool: revisit the compatibility constraints above first. The current prompts assume
  exactly one.
