# Configuration

grillspec reads two TOML files and merges them **per key**: the project file wins over
the user file, which wins over the built-in defaults.

| Level | Path | Typical content |
|---|---|---|
| Project | `.grillspec/config.toml` (committed) | team choices: spec backend, artifact language |
| User | `$XDG_CONFIG_HOME/grillspec/config.toml`, else `~/.config/grillspec/config.toml`; on Windows `%APPDATA%\grillspec\config.toml` | personal defaults: grilling depth, council members |

## Keys

```toml
version = 1

[spec]
backend = "openspec"          # openspec | superpowers — set by init
artifacts_language = "auto"   # auto | a language tag such as en, ru

[grill]
depth = "standard"            # quick | standard | deep

[council]
enabled = "ask"               # ask | yes | no
members = []                  # e.g. ["role:devil", "role:simplicity", "cli:gemini"]

[gates]
enabled = true
```

| Key | Default | Meaning |
|---|---|---|
| `spec.backend` | unset until `init` | `openspec`: living specs in `openspec/specs/` plus a change folder per change. `superpowers`: one dated spec and one plan per change in `docs/grillspec/`. |
| `spec.artifacts_language` | `auto` | Language of specs and plans. `auto` follows the project's existing docs, or the conversation in an empty repository. OpenSpec keywords stay English either way. |
| `grill.depth` | `standard` | How deep grilling goes: `quick` asks in rounds with a budget of about 5 questions, `standard` one at a time with about 15, `deep` without a budget. A change starts in the `grill` phase (`grillspec new`) and leaves it with `grillspec approve grill`; see [How grilling works](how-it-works/grilling.md). |
| `council.enabled` | `ask` | Whether grilling consults a council of independent perspectives; `ask` asks at the start of each grilling session. |
| `council.members` | `[]` | Default council members. |
| `gates.enabled` | `true` | Whether phase gates are active. |

## The `version` key

Every grillspec file carries `version = 1`. A file with another version is rejected
with a message naming the file, so an old grillspec never misreads a newer format.

## Warnings and errors

- **Unknown key** → a warning naming the key and the file; grillspec continues. A
  config written by a newer grillspec does not break an older one.
- **Invalid value** (for example `depth = "extreme"`) → an error naming the key, the
  file and the allowed values.
- **Malformed TOML** → an error naming the file and the line.

At session start, errors never block the agent: they appear as warnings in the context
(see [How the bootstrap works](how-it-works/bootstrap.md)).
