# Contributing to grillspec

Thank you for helping. grillspec is small on purpose: every skill line is read by an
agent on every activation, so a contribution is judged by what it changes in an
agent's behaviour, not by how much it adds.

## Ground rules

- Commit messages and PR titles follow [Conventional Commits](https://www.conventionalcommits.org/).
  PRs are squash-merged; the PR title becomes the commit message.
- No AI attribution in commits or PR descriptions (`Co-Authored-By: Claude`,
  "Generated with …"). CI rejects it. Use agents freely; credit is yours.
- Runtime code is Python 3.11–3.15 with the standard library only, and must work on
  Linux, macOS and Windows. Skills, hooks and docs never call `python3` directly:
  they go through `scripts/grillspec` / `scripts/grillspec.cmd`.
- Every user-facing doc change lands in both `docs/en` and `docs/ru`.

## Set up

```bash
uv sync
```

## Check before you push

```bash
uv run ruff check . && uv run ruff format --check . && uv run basedpyright && uv run pytest
uv run python scripts/lint_skills.py
uv run python scripts/bump_version.py --check
uv run python scripts/check_docs_mirror.py
```

## How work is planned here

grillspec develops itself with grillspec: a change that involves a decision is grilled,
specced and planned before code. Those working documents stay with whoever writes them
(`private/` is git-ignored); the PR description carries what reviewers need.
Typos, renames and other changes without a choice in them need none of it.

## Changing a skill

Skills are behaviour, so they are tested like behaviour:

1. Write down the failure you want to fix: the prompt, what the agent did, and what it
   should have done.
2. Reproduce it without your change (an eval case in `tests/evals/` or a pressure
   scenario in `tests/pressure/`).
3. Change the skill, rerun, and show the difference in the PR.

Keep skill frontmatter to `name` and `description`, English only. The router
(`skills/using-grillspec`) stays within 150 lines.

## Adding a harness

1. Add its skill directory and context file to `src/grillspec/install/_targets.py`.
2. If it has session-start hooks, add its output shape to
   `src/grillspec/hooks/_session_start.py`, a hook config under `hooks/`, and a branch
   in `hooks/run-hook.cmd` for the no-Python message.
3. Add `skills/using-grillspec/references/<harness>-tools.md`.
4. Add the harness to `tests/smoke/smoke.sh` and record a run in `tests/smoke/README.md`.

## Releasing (maintainer)

Before the tag, on the release branch:

1. `uv run python scripts/bump_version.py X.Y.Z`; move `[Unreleased]` in `CHANGELOG.md`
   under `## [X.Y.Z] - YYYY-MM-DD` and update the compare links at the bottom.
2. CI is green, and locally `claude plugin validate --strict .` passes.
3. Pressure evals: `claude plugin eval . --eval-dir tests/evals --scaffold --tag pressure
   --ablation none --no-publish --trust-plugin --allow-tools Edit Write`. Every case
   averages at least 0.8; record the scores in the release PR description before
   it is merged.
4. Smoke runs: `tests/smoke/smoke.sh` and `tests/smoke/smoke_gates.sh` for Claude Code
   and Cursor must PASS; every other harness gets a dated row in
   `tests/smoke/README.md` saying why it was not run.
5. `uv run python scripts/check_tokens.py` passes; after a harness or model update, run
   `tests/benchmark/overhead.sh claude` and add a row to `docs/*/tokens.md`.
6. Merge the release PR as `chore: release X.Y.Z`.

Publishing (the owner, once per step):

1. First release only: on pypi.org add a pending trusted publisher for `grillspec`
   (repository `forbxpg/grillspec`, workflow `release.yml`, environment `pypi`), and
   create the `pypi` environment in the repository settings.
2. Tag `vX.Y.Z` on main and push it; the release workflow checks the version and the
   changelog, builds, publishes to PyPI and creates the GitHub release.
3. Check the PyPI page, `uvx grillspec version`, and the GitHub release notes.
4. Catalogues: the repository itself is the Claude Code and Codex marketplace; submit
   to the Anthropic plugin directory and other catalogues with the README summary.
