# Contributing to grillspec

Thank you for helping. grillspec is small on purpose: every skill line is read by an
agent on every activation, so a contribution is judged by what it changes in an
agent's behaviour, not by how much it adds.

## Ground rules

- Commit messages and PR titles follow [Conventional Commits](https://www.conventionalcommits.org/).
  PRs are squash-merged; the PR title becomes the commit message.
- No AI attribution in commits or PR descriptions (`Co-Authored-By: Claude`,
  "Generated with …"). CI rejects it. Use agents freely; credit is yours.
- Runtime code is Python ≥ 3.11 with the standard library only.
- Every user-facing doc change lands in both `docs/en` and `docs/ru`.

## Set up

```bash
uv sync
```

## Check before you push

```bash
uv run ruff check . && uv run ruff format --check . && uv run basedpyright && uv run pytest
python3 scripts/lint_skills.py
python3 scripts/bump_version.py --check
python3 scripts/check_docs_mirror.py
```

## How work is planned here

grillspec develops itself with grillspec. A change that involves a decision gets a
spec in `docs/grillspec/specs/` and a plan in `docs/grillspec/plans/` before code.
Typos, renames and other changes without a choice in them do not.

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
4. Add `tests/smoke/<harness>.sh` and record a run in `tests/smoke/README.md`.

## Releasing (maintainer)

1. `python3 scripts/bump_version.py X.Y.Z`, move `[Unreleased]` in `CHANGELOG.md` under
   the new version, commit `chore: release X.Y.Z`.
2. Run `claude plugin validate --strict .` locally.
3. Tag `vX.Y.Z` and push the tag; the release workflow builds, publishes to PyPI and
   creates the GitHub release.
