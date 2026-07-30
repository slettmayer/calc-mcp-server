# Tech Stack

## Purpose
Documents the languages, frameworks, build tooling, and — most importantly for this repo — the
dependency policy.

## Responsibilities
- Listing runtime and development dependencies with their version bounds
- Documenting the dependency policy and why it exists
- Describing the build backend and versioning scheme
- Listing CI tooling

## Non-Responsibilities
- Release process (see [RELEASING.md](RELEASING.md))
- Module structure (see [ARCHITECTURE.md](ARCHITECTURE.md))

## Overview

### Language
- Python 3.12+ (`requires-python = ">=3.12"`)
- `from __future__ import annotations` in every file
- A `.python-version` pinning 3.12 keeps local development on the same interpreter CI uses. This is not
  cosmetic: stdlib `math` error messages were reworded after 3.12, and a test asserting on them would
  pass locally and fail in CI.

### Runtime dependencies

**Exactly one, upper-bounded.**

| Package | Bound | Used by |
|---|---|---|
| `mcp[cli]` | `>=2,<3` | `server.py` only |

Everything else is the standard library: `ast`, `math`, `operator`, `logging`.

### Dependency policy

This is the reason the repo exists, so it is a rule and not a preference.

- **Every dependency carries an upper bound.** The package this server replaces declared
  `mcp>=1.4.1` with none. When the SDK released v2 and removed `mcp.server.fastmcp`, every
  `uvx …@latest` install of it began crashing on import — and took down every other server sharing
  the MCP proxy process.
- **`uv.lock` is regenerated in the same commit as any `pyproject.toml` dependency change.** The lock
  records the spec in `requires-dist`; if the two disagree, `uv sync --locked` fails CI. That failure
  is the guardrail working.
- **Adding a runtime dependency needs a reason that survives the question "what happens when this is
  abandoned?"** A hand-rolled evaluator was chosen over `simpleeval` on exactly this ground — see
  [SAFE-EVALUATION.md](SAFE-EVALUATION.md).

### Development dependencies

Declared in the `dev` dependency group, so CI installs the same versions from `uv.lock` that a
developer has locally.

| Package | Bound | Purpose |
|---|---|---|
| `pytest` | `>=9.0.3` | Test runner |
| `pytest-asyncio` | `>=1.3.0` | Async test support (`asyncio_mode = "auto"`) |
| `ruff` | `>=0.16.0` | Lint + format |

`ruff` is deliberately in the lock rather than a bare `pip install ruff` in CI: an unpinned install
means a ruff release can fail the build with no change to this repo, and CI can lint with a different
version than any developer.

### Build and versioning
- `hatchling` + `hatch-vcs`, `dynamic = ["version"]`, `source = "vcs"`
- The version is derived from the git tag; `src/calc_mcp_server/_version.py` is generated at build time
  and gitignored. There is no version string to edit.
- `src/` layout with a `py.typed` marker

### Tooling
- `uv` for environments and locking
- `ruff` — `target-version = "py312"`, `line-length = 88`, lint rules `E,W,F,I,UP,B,SIM`
- `pytest` with `asyncio_mode = "auto"`. No `integration` marker: nothing external is contacted, so the
  whole suite runs in CI.

### CI
GitHub Actions, three workflows:

| Workflow | Trigger | Does |
|---|---|---|
| `validate.yml` | push to `main`, any PR | `ruff check` + `ruff format --check` + `pytest`, gated by a `gate` job |
| `release.yml` | `v*` tag | Build, verify tag matches version, publish to PyPI (Trusted Publishing/OIDC), GitHub Release, MCP Registry |
| `auto-release.yml` | merged `dependabot/uv/*` PR, or manual dispatch | Prepare changelog, commit, tag |

Both `validate` jobs use `astral-sh/setup-uv` with `uv sync --locked`. **Never `pip install -e .`** — it
ignores `uv.lock` and resolves fresh, which is how the original breakage reached CI unnoticed.

Dependabot runs weekly for the `uv` and `github-actions` ecosystems, grouped.

## Known Risks
- A single runtime dependency means the `mcp` SDK's v3 release is the one upgrade that will ever matter
  here. The `<3` bound turns that into a deliberate migration rather than a silent break.
- `hatch-vcs` needs full git history in CI (`fetch-depth: 0`); a shallow checkout produces a wrong
  version rather than an error.

## Extension Guidelines
- New runtime dependency: bound it, justify it, regenerate `uv.lock` in the same commit.
- New dev tool: add it to the `dev` group so CI and local stay identical. Do not install it ad hoc in a
  workflow step.
