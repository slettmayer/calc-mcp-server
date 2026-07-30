# Calculator MCP Server

An MCP server that does arithmetic, exactly — so an LLM does not have to do it mentally.

One tool, `calculate`, evaluating expressions against a hand-rolled AST allowlist. No `eval()`, no
`sympy`, no unbounded dependencies.

```
2 + 3 * (4 - 1) / 2 ** 2   ->  4.25
sqrt(16) + sin(pi/2)       ->  5.0
123456789 * 987654321      ->  121932631112635269
```

## Why this exists

The widely-used `mcp-server-calculator` package is abandoned (last commit May 2025) and declares
`mcp>=1.4.1` with no upper bound. When the MCP Python SDK released v2 and removed
`mcp.server.fastmcp`, every `uvx …@latest` install of it started crashing on import — which took down
the entire MCP proxy hosting it, and every other server alongside it.

No maintained Python replacement exists. The one actively-maintained npm calculator computes in
float64, so `123456789 * 987654321` comes back as `121932631112635260` — off by 9. That is a poor
trait in a tool whose whole purpose is that the model should not be doing the arithmetic itself.

So this server:

- **bounds its one dependency** (`mcp[cli]>=2,<3`) — the failure above cannot recur here;
- **keeps integers exact** at any size, never coercing to float;
- **bounds resource use**, not just code execution — see below.

## Safety

Two problems, and most calculator servers only solve the first.

**Code execution.** Expressions are parsed with `ast.parse` and walked against an explicit allowlist of
node types. `Attribute` is not on it, so `(1).__class__.__bases__` is rejected. A `Call` is only
evaluated when its target is a bare name in the function allowlist, so `__import__('os').system(…)` is
rejected before any argument is even evaluated.

**Resource exhaustion.** An allowlist alone still lets `9**9**9` occupy the process for minutes on
unbounded bignum exponentiation — the incumbent hangs for over five seconds on it. Four caps close
that: expression length (500 chars), nesting depth (32), result size (4300 digits, checked on the
operands *before* exponentiating), and factorial argument (1000).

Full detail in [docs/tech/SAFE-EVALUATION.md](docs/tech/SAFE-EVALUATION.md).

## Install

```bash
uvx calc-mcp-server
```

Pin it. Do not add `@latest` — that is how the package this replaces broke.

## Configure

As a stdio MCP server:

```json
{
  "mcpServers": {
    "calculator": {
      "command": "uvx",
      "args": ["calc-mcp-server"]
    }
  }
}
```

## The `calculate` tool

| Argument | Type | Description |
|---|---|---|
| `expression` | `str` | The expression to evaluate |

Returns the result as a string, or a line starting with `Error: ` explaining why the expression was
rejected. The tool never raises, so a bad expression is an answer the agent can read back rather than a
tool-call failure.

**Operators** — `+` `-` `*` `/` `//` `%` `**`, parentheses, unary `+`/`-`. `^` is accepted as a power
operator, and `×` `·` `÷` `−` are accepted as their ASCII equivalents (speech-to-text produces them).

**Constants** — `pi`, `e`, `tau`.

**Functions** — `abs` `round` `min` `max` `sqrt` `exp` `log` `log2` `log10` `sin` `cos` `tan` `asin`
`acos` `atan` `atan2` `degrees` `radians` `hypot` `floor` `ceil` `factorial` `gcd` `lcm`.

**Results** — integer arithmetic returns an exact integer of any size. Floats are rendered at 12
significant digits, which removes IEEE-754 representation noise (`0.1 + 0.2` reads `0.3`, not
`0.30000000000000004`) while keeping far more precision than a calculator result is used at. A whole
float keeps its `.0`, so `8 / 2` reads `4.0` and stays distinct from the exact integer `4`.

## Development

```bash
uv sync
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format .
```

See [AGENTS.md](AGENTS.md) for the project guide and [docs/](docs/README.md) for the full
documentation set.

## License

MIT — see [LICENSE](LICENSE).
