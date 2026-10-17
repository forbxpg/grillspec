# OpenSpec change layout

`openspec/changes/<id>/` holds:

| File | Content |
|---|---|
| `proposal.md` | `## Why` (50-1000 characters), `## What Changes`, `## Capabilities`, `## Impact` |
| `specs/<capability>/spec.md` | one delta file per capability the change touches |
| `design.md` | the decision log (written by the grill), plus `## Goals / Non-Goals` and `## Open questions` |
| `.openspec.yaml` | `schema: spec-driven`, `created`, and `skip_specs: true` only when no behaviour changes |

## proposal.md

````markdown
## Why

One sender can overwhelm webhook receivers with bursts of deliveries, and receivers
start rejecting every request.

## What Changes

- Limit deliveries per receiver to 10 per second.

## Capabilities

### New Capabilities
- `rate-limits`: per-receiver delivery limits.

### Modified Capabilities
- `delivery`: failed deliveries are retried with backoff.

## Impact

The webhook sender and its queue.
````

## Delta for a new capability

````markdown
## Purpose

Keeps webhook receivers safe from bursts of deliveries sent by one sender.

## ADDED Requirements

### Requirement: Burst limit
The sender SHALL reject a delivery that exceeds 10 deliveries per second to one
receiver.

#### Scenario: RL-1 burst exceeded
- **WHEN** 11 deliveries to one receiver are queued within one second
- **THEN** the eleventh is rejected with a rate-limit error
````

`## Purpose` (at least 50 characters) appears only for a new capability.

## Delta for an existing capability

````markdown
## MODIFIED Requirements

### Requirement: Retry failed deliveries
(the whole block copied from openspec/specs/delivery/spec.md, then edited;
scenarios keep their IDs, new scenarios take this change's tag)

## REMOVED Requirements

### Requirement: Fixed retry interval
**Reason**: Replaced by exponential backoff.
**Migration**: Nothing to do; retries now back off automatically.

## RENAMED Requirements

- FROM: `### Requirement: Retry`
- TO: `### Requirement: Retry failed deliveries`
````

The requirement header is the key OpenSpec matches on archive: copy it exactly.
