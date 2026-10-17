---
type: regex
weight: 1
pattern: "approve|одобр|decide|decision|реши"
flags: i
---

The agent stops for the user: it asks for approval of the spec, or (when the
builder-check found gaps) puts the open decisions to the user. It never approves the
spec itself.
