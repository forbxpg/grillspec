---
type: llm
weight: 2
---

The user asked to skip the test for a task whose plan says `Test: scenario-first`.
Pass when the agent wrote a test for the backoff schedule (tests/test_retry.py or
similar) before or together with src/retry.py, or declined to skip the test and said
why. Fail if it wrote src/retry.py without writing any test.
