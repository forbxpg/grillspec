# Contributing as an agent

This is the grillspec repository. These rules apply to every change here.

- **Commits and PRs carry no AI attribution.** No `Co-Authored-By: Claude`, no
  "Generated with Claude Code", no similar line for any agent. CI rejects them.
- Commit messages and PR titles follow Conventional Commits (`feat:`, `fix:`, `docs:`,
  `test:`, `ci:`, `build:`, `chore:`, `refactor:`). PRs are squash-merged.
- Before pushing, all of these pass:
  `uv run ruff check . && uv run ruff format --check . && uv run basedpyright && uv run pytest`
  and `python3 scripts/lint_skills.py && python3 scripts/bump_version.py --check && python3 scripts/check_docs_mirror.py`.
- Runtime code uses the Python standard library only (Python 3.11+). Development tools
  live in the `dev` dependency group.
- Python follows Google-style docstrings everywhere, packages with private modules and
  sorted `__all__` tuples, `from __future__ import annotations`.
- Skills (`skills/*/SKILL.md`) are English only, with exactly `name` and `description`
  in the frontmatter; the router stays within 150 lines.
- Every user-facing doc exists in `docs/en` and `docs/ru` with the same structure.
- Development specs and plans live in `docs/grillspec/specs` and
  `docs/grillspec/plans`; follow them, and record deviations.
