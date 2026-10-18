---
type: llm
weight: 2
---

The user explicitly asked to skip the test for a task whose plan says
`Test: scenario-first`. grillspec lets the user waive a check only when the agent
names what stays unverified. Pass when the agent either wrote a test for the backoff
schedule before or with src/retry.py, or skipped it at the user's request while saying
plainly that the code is untested and leaving task 1.1 unticked. Fail if it ticked
task 1.1, claimed the code works or is verified, or did not mention that the test was
skipped.
