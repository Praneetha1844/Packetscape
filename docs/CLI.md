# Command-line reference

```
packetscape [--version] {run,validate} ...
```

Exit codes: `0` success, `2` error (invalid scenario, no route, unwritable output, missing matplotlib). The message goes to standard error. `argparse` also exits with `2` on a usage error.

## `packetscape validate FILE`

Parses the scenario and builds the simulation (including routes) without running it. Prints `FILE: OK` on success.

## `packetscape run FILE`

| Option | Meaning |
|---|---|
| `--out DIR` | Write `flows.csv` and `cwnd.csv` to `DIR` (created if needed) |
| `--plots` | Also write `throughput.png`, `latency.png` and `cwnd.png`. Needs `--out` and the `plots` extra (matplotlib). |
| `--seed N` | Override the scenario's seed |

The run prints a per-flow table and the Jain fairness index over all flows.

### `flows.csv`

One row per flow: `flow_id, kind, sent_packets, delivered_packets, delivered_bytes, dropped_queue, dropped_loss, throughput_mbps, loss_ratio, delay_mean_ms, delay_p50_ms, delay_p95_ms, delay_p99_ms`. Delay columns are empty when no packet was delivered. Definitions of throughput, loss and delay are in [model-and-limits](model-and-limits.md#semantics-worth-knowing).

### `cwnd.csv`

`flow_id, time_s, cwnd_packets` for every TCP flow, written when the window changes.

## Reproducibility

The same scenario file and seed always produce the same output. Quote the file, the seed and the command with any number you report. See [ADR 0002](adr/0002-seeded-per-component-randomness.md).
