# Releasing

> How a version gets published, and where the changelog fits. Read this before cutting a release or
> changing `auto-release.yml` / `release.yml`.

## The version lives in git, not the source tree

`hatch-vcs` derives the version from the git tag. There is **no** version string to edit — no
`__version__` literal, no `version =` in `pyproject.toml`. `src/calc_mcp_server/_version.py` is generated
at build time and gitignored.

Consequence: **creating the tag is the release.** Everything else follows from it.

## Writing changelog entries

Add entries under `## Unreleased` in `CHANGELOG.md` as work lands, in the same PR as the change. Say what
changed and why it mattered; the diff already shows the how.

You do **not** rename `## Unreleased` yourself — the release workflow does it (see below). Renaming it by
hand is harmless (the script detects an existing section and leaves it alone), but unnecessary.

A `Changelog reminder` job warns when a PR touches `src/` without touching `CHANGELOG.md`. It is advisory:
it never blocks a merge, and it skips Dependabot PRs and anything labelled `no-changelog`.

## Cutting a release

Run the **Auto Release** workflow via `workflow_dispatch`:

- leave `version` empty → bumps the patch from the highest existing tag
- set `version` (e.g. `v0.2.0`) → releases exactly that, for a deliberate minor or major

The workflow then:

1. resolves and validates the version, failing if that tag already exists
2. runs `scripts/changelog_release.py`, which moves the `## Unreleased` entries under
   `## <version> - <date>` and appends a `- Build:` line per Dependabot commit since the last tag
3. commits `CHANGELOG.md` to `main` — only if it actually changed
4. tags **that** commit and pushes

Step 4's order matters: the tag must point at the commit containing the changelog, or every release ships
without its own section.

Pushing the `v*` tag triggers **Release**, which builds, verifies the tag matches the built version,
publishes to PyPI via Trusted Publishing, creates the GitHub Release, and publishes to the MCP Registry.
`server.json`'s version is rewritten from the tag at publish time, so the `0.1.0` in the committed file is
a placeholder and does not need updating.

### The first release

`v0.1.0` must be cut by **manual dispatch with the version set explicitly**. A `feat/*` branch does not
trigger `auto-release.yml` — only a merged `dependabot/uv/*` PR or a dispatch does — and leaving the input
empty would produce `v0.0.1`.

Before it can succeed, two things must exist and cannot be created from this repo:

- a **pending publisher** on PyPI for `calc-mcp-server`, pointing at `slettmayer/calc-mcp-server`,
  workflow `release.yml`, environment `pypi`
- the `GH_ACTION_APP_ID` and `GH_ACTION_APP_PRIVATE_KEY` repository secrets, for the App that pushes the
  changelog commit past the `main` ruleset

## What Dependabot triggers

Merging a Dependabot PR from the **`uv`** ecosystem (`dependabot/uv/*`) auto-cuts a patch release — those
change the published package. **`github-actions`** bumps do not; they merge without releasing.

A dependency **major** bump deserves a deliberate minor release via dispatch rather than the automatic
patch, since it changes what consumers resolve.

## Changing the changelog script

`scripts/changelog_release.py` is covered by `tests/test_changelog_release.py`, which fakes git so no
repository fixture is needed. Run `uv run pytest tests/test_changelog_release.py`.

## Gotchas

- The `main` ruleset requires the `gate` status check and squash merges. It is a **ruleset**, not classic
  branch protection — the classic API returns 404 and reads as "not protected".
- Dependabot has silently ignored `@dependabot rebase` in the sibling repos while GitHub showed stale
  checks as current. Use `gh pr update-branch <n>` and confirm `completedAt` postdates the push before
  merging.
- `uv.lock` records the dependency spec in `requires-dist`, so it must be regenerated in the same commit
  as any `pyproject.toml` dependency change or `uv sync --locked` fails CI.
