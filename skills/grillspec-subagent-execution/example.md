# Subagent-driven execution — example workflow

```
You: I'm using Subagent-Driven Development to execute this plan.

[Setup: worktree verified]
[Read plan file once: docs/grillspec/plans/2026-10-17-feature.md]
[Resolve workspace: grillspec exec workspace — no ledger lines yet, fresh start]
[Create todos for all tasks]

Task 1.1: Hook installation script

[Run grillspec exec start 1.1; dispatch implementer with brief + report paths + context]

Implementer: "Before I begin - should the hook be installed at user or system level?"

You: "User level (~/.config/app/hooks/)"

Implementer: [Later]
  - Implemented install-hook command
  - Added tests, 5/5 passing
  - Self-review: Found I missed --force flag, added it
  - Committed

[Run grillspec exec review-package BASE HEAD; dispatch task reviewer with the printed path]
Task reviewer: Spec ✅ - all requirements met, nothing extra.
  Strengths: Good test coverage, clean. Issues: None. Task quality: Approved.

[grillspec exec done 1.1 a1b2c3d -- npm test → box ticked; Ledger: Task 1.1: complete (commits a1b2c3d..d4e5f6a, …); Task 1.1: review clean]

Task 1.2: Recovery modes

[Run grillspec exec start 1.2; dispatch implementer with brief + report paths + context]

Implementer: [No questions]
  - Added verify/repair modes
  - 8/8 tests passing
  - Committed

[Run grillspec exec review-package BASE HEAD; dispatch task reviewer with the printed path]
Task reviewer: Spec ❌:
  - Missing: Progress reporting (spec says "report every 100 items")
  Issues (Important): Magic number (100)

[Fix round 1: resume the implementer with both findings]
Implementer: Added progress reporting, extracted PROGRESS_INTERVAL constant.
  Re-ran test/recovery.test.js — 10/10 passing. Fix report appended.

[Run grillspec exec review-package FIX_BASE HEAD; dispatch scoped re-review]
Re-reviewer: Missing progress reporting — ADDRESSED (src/recovery.js:41).
  Magic number — ADDRESSED (src/recovery.js:7). New breakage: none.
  Verdict: all findings addressed.

[Ledger: Task 1.2: fix round 1/5 (2 addressed, 0 open; commits d4e5f6a..b7c8d9e)]
[grillspec exec done 1.2 d4e5f6a -- npm test → box ticked; Ledger: Task 1.2: complete (…); Task 1.2: review clean]

...

[After all tasks]
[Run grillspec exec review-package MERGE_BASE HEAD; dispatch final code-reviewer, most capable model]
Final reviewer: All requirements met. Deferred minors triaged: none block merge.

[Delete this plan's workspace — the record now lives in git]

Done! Using grillspec-finishing.
```
