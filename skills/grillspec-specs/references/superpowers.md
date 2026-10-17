# Superpowers spec layout

One file, `docs/grillspec/specs/<id>.md`. The grill already wrote the title and the
decision log; add the other sections around it and leave the log as it is.

````markdown
# 2026-10-17-rate-limits

## Intent

Stop one sender from overwhelming webhook receivers with bursts of deliveries.

### Non-goals
- Per-receiver quotas.

## Decision log

… (written by the grill; do not edit Settled lines)

## Requirements

### Requirement: Burst limit
The sender SHALL reject a delivery that exceeds 10 deliveries per second to one
receiver.

#### Scenario: RL-1 burst exceeded
- **WHEN** 11 deliveries to one receiver are queued within one second
- **THEN** the eleventh is rejected with a rate-limit error

#### Scenario: RL-2 burst allowed
- **WHEN** 10 deliveries to one receiver are queued within one second
- **THEN** all 10 are sent

## Open questions

- Q4 Window alignment (calendar seconds or sliding): recommend sliding; decide before
  the plan.
````

`## Open questions` exists only when deferred items remain. There is no Testing
section: the plan gives each task its test strategy.
