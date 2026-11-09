# Architecture

Packetscape is a single-process, single-threaded discrete-event simulation. Everything that happens is an event on one clock; nothing runs concurrently, which is what makes runs deterministic.

## Component view

```mermaid
flowchart LR
    YAML[Scenario YAML] --> CFG[config.py<br/>validate + dataclasses]
    CFG --> SIM[simulation.py<br/>assemble]
    SIM --> TOPO[topology.py<br/>routes]
    SIM --> NET[network.py<br/>links + forwarding]
    SIM --> TRN[transport.py<br/>sources, TCP-like]
    TRN --> CC[congestion.py]
    NET --> Q[queues.py]
    SCH[events.py<br/>scheduler] --- NET
    SCH --- TRN
    NET --> MET[metrics.py]
    TRN --> MET
    MET --> REP[reporting.py / plots.py]
    REP --> OUT[(CSV, PNG, console)]
```

Dependencies point downwards: `config` knows nothing about the simulation, `queues` and `congestion` know nothing about the scheduler, and `metrics` is a passive sink.

## Packet life cycle

```mermaid
sequenceDiagram
    participant S as TcpSender
    participant L1 as Link s to r
    participant L2 as Link r to d
    participant R as TcpReceiver
    S->>L1: inject(packet)
    L1->>L1: enqueue (drop-tail or RED)
    L1->>L1: transmit (size / bandwidth)
    L1->>L2: arrive after propagation delay
    L2->>R: deliver to endpoint
    R->>S: cumulative ACK on the reverse path
    S->>S: update window, RTO, retransmit if needed
```

A packet carries its full path and the index of the node that holds it. `Network.forward` either hands it to the next link or, at the last node, to the endpoint registered for `(flow_id, is_ack)`.

## Link model

Each direction of a physical link is a separate `Link` with its own queue:

1. `send()` offers the packet to the queue. A rejected packet is recorded as a queue drop.
2. If the transmitter is idle it dequeues the head packet and schedules the end of serialization after `size_bytes * 8 / bandwidth`.
3. When serialization ends, the next packet starts transmitting immediately and the finished packet is scheduled to arrive after the propagation delay.
4. On arrival the link may drop the packet with the configured random loss probability; otherwise the network forwards it.

## Transport model

`TcpSender` keeps `snd_una` (lowest unacknowledged sequence), `next_seq`, a duplicate-ACK counter, a `recover` marker and a retransmission timer.

- **New ACK:** advance `snd_una`, take an RTT sample (skipped for retransmitted packets), tell the controller, re-arm or cancel the timer, send more data while `inflight < floor(cwnd)`.
- **Duplicate ACK:** after three, and only once per recovery window, notify the controller and retransmit `snd_una`.
- **Timeout:** notify the controller, double the RTO (capped), retransmit `snd_una`.

`CongestionControl` implementations are small state machines with `on_ack`, `on_fast_retransmit` and `on_timeout`, so adding an algorithm does not touch the sender.

## Randomness

Every stochastic component (each queue, each link, each Poisson source) draws from its own `random.Random` stream derived from `(seed, component name)`. See [ADR 0002](adr/0002-seeded-per-component-randomness.md).

## Extension points

| To add | Implement | Register in |
|---|---|---|
| A queue discipline | `QueueDiscipline` in `queues.py` | `make_queue` in `simulation.py`, `QUEUE_TYPES` in `config.py` |
| A congestion controller | `CongestionControl` in `congestion.py` | `make_congestion_control`, `CC_NAMES` in `config.py` |
| A traffic source | A class with `start()` that schedules injections | `Simulation._build_flows` |
| A metric | A method on `MetricsCollector` plus a field on `FlowSummary` | `reporting.py` |

## Testing approach

- Unit tests for each module with hand-computed expectations (for example, serialization plus propagation time on a link).
- Behavioural tests for algorithms (window growth, reduction, queue thresholds) using fixed-value random streams.
- Scenario tests: a finite transfer over a clean link delivers every packet, a lossy link still delivers every packet eventually, identical seeds give identical results, and every example file builds.
