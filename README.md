# Packetscape

A discrete-event network simulator for comparing **congestion-control** and **queue-management** strategies on small, configurable topologies. Scenarios are plain YAML files, runs are reproducible from a seed, and results are exported as CSV and optional plots.

> **Status:** implementation and test suite included; benchmarks not yet published. This is a compact teaching and experimentation tool, not a replacement for ns-3 or a model of any real operating-system network stack. See [model and limits](docs/model-and-limits.md).

## Why this exists

Congestion control is easy to describe and hard to build intuition for. Packetscape makes the moving parts small enough to read end to end: a scheduler, links with finite bandwidth and queues, a TCP-like sender, and the metrics that show what a policy change does (throughput, loss, delay percentiles and fairness).

## Features

| Area | What is implemented |
|---|---|
| Simulation core | Priority-queue event scheduler with stable ordering of simultaneous events |
| Topology | Named nodes, bidirectional links (bandwidth, delay, random loss), hop-count shortest-path routing |
| Queues | Drop-tail FIFO, Random Early Detection (RED) |
| Transport | Packet-granular TCP-like sender and receiver: cumulative ACKs, fast retransmit, retransmission timer (RFC 6298 style) |
| Congestion control | Fixed window, AIMD (Reno-like), simplified CUBIC-style |
| Traffic sources | TCP-like bulk transfer, constant bit rate, Poisson |
| Metrics | Throughput, loss ratio, one-way delay (mean, p50, p95, p99), Jain's fairness index, congestion-window traces |
| Reproducibility | One seed per scenario, independent RNG stream per component |
| Interface | `packetscape run`, `packetscape validate`, CSV export, optional matplotlib plots |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,plots]"

packetscape validate examples/dumbbell_aimd.yaml
packetscape run examples/dumbbell_aimd.yaml --out results/aimd --plots
```

The run prints a per-flow summary table and writes `flows.csv`, `cwnd.csv` and (with `--plots`) `throughput.png`, `latency.png` and `cwnd.png` to the output directory.

Docker (written for convenience, not part of the verification of this repository):

```bash
docker build -t packetscape .
docker run --rm -v "$PWD/results:/tmp/results" packetscape
```

## Scenario format

```yaml
seed: 42                 # integer, default 0
duration: 30             # simulated seconds
nodes: [s1, s2, r1, r2, d1, d2]
links:
  - {a: s1, b: r1, bandwidth_mbps: 100, delay_ms: 2}
  - a: r1
    b: r2
    bandwidth_mbps: 10
    delay_ms: 20
    loss_prob: 0.0       # optional, in [0, 1)
    queue:               # optional, applied to each direction independently
      type: red          # droptail (default) | red
      capacity: 50       # packets
      min_threshold: 10  # red only; defaults to 25% of capacity
      max_threshold: 30  # red only; defaults to 75% of capacity
      max_p: 0.1
      weight: 0.02
flows:
  - {id: f1, src: s1, dst: d1, kind: tcp, cc: aimd}           # tcp | cbr | poisson
  - {id: v1, src: s2, dst: d2, kind: cbr, rate_mbps: 2, start: 5}
```

Unknown keys and invalid values are rejected with the path of the offending field (for example `config.links[1].queue: thresholds must satisfy 0 < min < max <= capacity`). Two links between the same pair of nodes, `cc` or `window` on a non-TCP flow, and `window` without `cc: fixed` are errors. The full reference is in [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

Flow options: `start` and `stop` (seconds), `packet_size` (bytes, default 1000), `cc` (`fixed`, `aimd`, `cubic`; TCP only), `window` (packets; `fixed` only), `packets` (finite transfer size; TCP only), `rate_mbps` (CBR and Poisson only).

Quote node names that YAML would read as booleans (`"no"`, `"on"`, `"y"`).

## Included scenarios

| File | Question it lets you explore |
|---|---|
| `examples/dumbbell_aimd.yaml` | Two AIMD flows sharing a bottleneck with drop-tail |
| `examples/dumbbell_cubic.yaml` | Same topology with the CUBIC-style controller |
| `examples/red_vs_droptail.yaml` | Same topology with a RED bottleneck |
| `examples/tcp_vs_udp.yaml` | A TCP-like flow competing with constant-bit-rate traffic over a lossy link |

No results are published here yet. Run the scenarios to produce your own, and record the exact command and seed with any number you quote.

## Project layout

```
src/packetscape/
  events.py        scheduler and cancellable events
  packet.py        packet model
  queues.py        drop-tail and RED
  network.py       link serializer and forwarding
  topology.py      graph and shortest-path routing
  congestion.py    fixed, AIMD, CUBIC-style controllers
  transport.py     UDP-like sources, TCP-like sender and receiver
  metrics.py       collectors, percentiles, Jain's index
  config.py        scenario dataclasses and validation
  simulation.py    scenario assembly and execution
  reporting.py     CSV and text output
  plots.py         optional matplotlib figures
  cli.py           command-line interface
tests/             unit and scenario tests
docs/              architecture, decision records, model limits
examples/          scenario files
```

## Documentation

Everything is indexed in [docs/index.md](docs/index.md).

- [Architecture](docs/ARCHITECTURE.md)
- [Scenario reference](docs/CONFIGURATION.md) and [command line](docs/CLI.md)
- [Model assumptions and limits](docs/model-and-limits.md)
- [Relation to CCNA topics](docs/ccna-relation.md)
- Decision records: [event-driven design](docs/adr/0001-discrete-event-over-time-stepped.md), [seeded determinism](docs/adr/0002-seeded-per-component-randomness.md), [simplified transport](docs/adr/0003-simplified-packet-granular-transport.md)

## Development

```bash
make install   # editable install with dev and plot extras
make check     # ruff, mypy (strict) and pytest with coverage
```

CI (GitHub Actions) runs lint, type checks and tests on Python 3.10 to 3.12, then builds the package and the container image.

## Limitations

- Packet-granular windows and sequence numbers; no byte streams, no selective acknowledgements, no delayed ACKs.
- CUBIC is a simplified curve; there is no BBR, no ECN and no active queue management beyond RED.
- Static shortest-path routing only; no routing protocols.
- Queues are measured in packets, not bytes.
- ACKs share the reverse-direction queues with data but are not modelled with their own loss statistics beyond a counter.
- Single-threaded, pure Python; suitable for small scenarios, not for large-scale studies.

## Roadmap

- Additional controllers (a BBR-style model) and ECN marking.
- Byte-based queue limits.
- Multi-run experiment runner with seed sweeps and confidence intervals.
- Scenario comparison reports.

## License

MIT. See [LICENSE](LICENSE).
