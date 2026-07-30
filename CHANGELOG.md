# Changelog

The version of a release is derived from its git tag by `hatch-vcs`; there is no version string in the
source tree. Add entries under `## Unreleased` as you go — the release workflow moves them under the
version being cut, so you never rename that heading by hand. See
[docs/tech/RELEASING.md](docs/tech/RELEASING.md).

## Unreleased

## 0.1.1 - 2026-07-30

- Fixed: `server.json`'s description was 116 characters, and the MCP Registry rejects anything over 100.
  v0.1.0 therefore published to PyPI and created its GitHub Release, then failed at the registry step —
  which cannot be re-run, because the workflow checks out the immovable tag. Shortened to 93 characters.
- Added: `tests/test_server_json.py` validates `server.json` against the registry's constraints in CI,
  minutes before a release rather than during one. The description limit is not in the JSON schema the
  file references, so nothing else in the toolchain catches it.

## 0.1.0 - 2026-07-30

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
- Fixed: the CI test step no longer passes `-m "not integration"`. This repo contacts nothing external
  and so defines no `integration` marker, and the flag disagreed with the `pytest tests/ -v` documented
  in `AGENTS.md` and `TESTING.md` — the kind of drift that makes CI look like it covers more than it
  does.

