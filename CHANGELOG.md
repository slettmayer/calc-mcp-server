# Changelog

The version of a release is derived from its git tag by `hatch-vcs`; there is no version string in the
source tree. Add entries under `## Unreleased` as you go — the release workflow moves them under the
version being cut, so you never rename that heading by hand. See
[docs/tech/RELEASING.md](docs/tech/RELEASING.md).

## Unreleased

- Added: initial release. A single `calculate` tool evaluating arithmetic expressions against a
  hand-rolled AST allowlist, replacing the abandoned `mcp-server-calculator` (last commit 2025-05-10),
  whose unbounded `mcp>=1.4.1` made `uvx …@latest` resolve the v2 SDK, crash on the removed
  `mcp.server.fastmcp`, and take the whole MCP proxy down with it.
- Added: resource caps the incumbent lacked — expression length, AST nesting depth, exponentiation
  result size and factorial argument. `9**9**9` hangs the incumbent for over five seconds; here it is
  rejected before any bignum work, from an estimate on the operands. See
  [SAFE-EVALUATION.md](docs/tech/SAFE-EVALUATION.md).
- Added: integer results stay exact at any size. The only actively-maintained alternative (the npm
  `@cyanheads/calculator-mcp-server`) computes in float64 and returns `121932631112635260` for
  `123456789 * 987654321` — off by 9, in a tool that exists so the model does not have to approximate.
- Added: an end-to-end stdio round-trip test that spawns the real entry point and speaks JSON-RPC to it.
  A unit-tested evaluator behind broken MCP wiring is precisely the failure that motivated this repo.
- Changed: floats render at 12 significant digits, so `0.1 + 0.2` reads `0.3` rather than
  `0.30000000000000004`. Whole floats keep their `.0`, so `8 / 2` stays visibly distinct from `4`.
