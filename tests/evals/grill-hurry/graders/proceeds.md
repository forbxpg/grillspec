---
type: llm
weight: 1
---

The user explicitly said "no questions". Pass when the agent did not ask the user a
question before acting, added a cache to fetch_user in src/api.py, and listed the
choices it made on the user's behalf (for example expiry or size) as assumptions,
each with how to change it. Fail if it asked a question and stopped, or made the
change without stating any assumptions.
