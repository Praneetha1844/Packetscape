# ADR 0001: Discrete-event simulation instead of a time-stepped loop

- Status: accepted
- Date: 2026-11-09

## Context

The simulator must model packets that take very different times to move: a serialization delay of microseconds on a fast link next to a retransmission timer of hundreds of milliseconds. Two designs were considered:

1. **Time-stepped:** advance a fixed `dt` and update every link and flow each step.
2. **Discrete-event:** keep a priority queue of future events and jump the clock to the next one.

## Decision

Use a discrete-event scheduler (`events.py`) built on `heapq`, with a monotonically increasing insertion counter as the tie-breaker for events scheduled at the same time.

## Consequences

- Accuracy does not depend on `dt`. A fixed step would either blur small serialization delays or waste work on idle periods.
- Cost scales with the number of events, not with simulated time, so quiet scenarios run quickly.
- Simultaneous events execute in insertion order, so runs are deterministic ([ADR 0002](0002-seeded-per-component-randomness.md)).
- Cancellation is lazy (a flag checked when the event is popped), which keeps `schedule` and `cancel` cheap but leaves cancelled entries in the heap until they surface. This matters mainly for retransmission timers that are re-armed on every ACK; memory is bounded by the number of re-arms in flight, which is acceptable at the scale this tool targets.
- Components must express behaviour as callbacks rather than loops, which makes the code a little less linear to read than a stepped model.
