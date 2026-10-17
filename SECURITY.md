# Security policy

grillspec runs hooks inside coding agents and edits files in your project, so a way to
make it run unintended commands or write outside the files it owns is a serious bug.

## Reporting

Report through GitHub: **Security → Report a vulnerability** on this repository. Do not
open a public issue for it. Include the harness and its version, the grillspec version
or commit, and the steps.

## What counts

- A hook or CLI command that runs something other than grillspec's own code.
- `init`, `install` or `uninstall` writing, editing or deleting a file they did not
  report or record.
- Anything else that breaks a promise in the README or the docs.

Instructions an agent follows from a malicious repository are a property of the agent,
not of grillspec, unless grillspec's own text makes them more likely.

## What happens next

We confirm receipt within 7 days and agree on a fix and a date. Disclosure is
coordinated and happens at the latest 90 days after the report. Reporters are credited
unless they ask otherwise.

## Supported versions

Until 1.0 only the latest release receives security fixes.
