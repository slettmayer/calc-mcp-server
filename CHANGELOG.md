# Changelog

The version of a release is derived from its git tag by `hatch-vcs`; there is no version string in the
source tree. Add entries under `## Unreleased` as you go — the release workflow moves them under the
version being cut, so you never rename that heading by hand. See
[docs/tech/RELEASING.md](docs/tech/RELEASING.md).

## Unreleased

## 0.1.4 - 2026-08-14

- Build: bump ruff in the python-dependencies group.

## 0.1.3 - 2026-08-08

- Fixed: the `calculate` tool docstring advertised three of the five operator aliases, omitting `·` and
  `−` (U+2212). The docstring is the tool description the model reads, so both were accepted by the
  evaluator but no agent would ever send them — a speech-to-text layer producing either got a capability
  that existed only on paper.
- Added: a test asserting every key of `OPERATOR_ALIASES` appears in the tool docstring, so widening the
  alias table without advertising it now fails CI instead of going unnoticed.
- Changed: `auto-release.yml` now passes `client-id` to `actions/create-github-app-token` instead of the
  deprecated `app-id`, reading a new `GH_ACTION_APP_CLIENT_ID` secret. Every run warned
  `Input 'app-id' has been deprecated`; the token it mints is what pushes the changelog commit past the
  `main` ruleset, so the input will not be left to be removed on the action's schedule.
- Build: bump ruff in the python-dependencies group.

## 0.1.2 - 2026-07-30

- Fixed: the README was missing the `<!-- mcp-name: io.github.slettmayer/calc-mcp-server -->` marker the
  MCP Registry uses to prove PyPI ownership, so v0.1.1 published to PyPI and then failed the registry
  with "ownership validation failed". Both sibling servers carry it; a fresh README did not.
- Added: a test asserting the marker is present and matches `server.json`'s name, alongside the
  description-length check. Both failures share a shape — the registry only validates at publish time,
  after the PyPI upload has already succeeded and the tag is immovable.
- Added: PyPI, Python and licence badges, matching the sibling servers.

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

