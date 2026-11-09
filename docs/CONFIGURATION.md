# Scenario reference

A scenario is a YAML file. Unknown keys are rejected, and every error names the path of the offending field, for example `config.flows[1].rate_mbps: must be > 0`. Use `packetscape validate FILE` to check a file without running it.

Units: bandwidth in Mb/s, delay in milliseconds, time in seconds, sizes in bytes, queue capacity in packets.

## Top level

| Key | Required | Default | Rules |
|---|---|---|---|
| `seed` | no | `0` | Integer. Overridable with `--seed`. |
| `duration` | yes | none | Number above 0: simulated seconds. |
| `nodes` | yes | none | List of at least two unique, non-empty strings. Quote names YAML reads as booleans (`"no"`, `"on"`). |
| `links` | yes | none | Non-empty list. At most one link per pair of nodes, in either order. |
| `flows` | yes | none | Non-empty list with unique `id` values. |

## Link

Each link is bidirectional. Every direction has its own queue and random stream.

| Key | Required | Default | Rules |
|---|---|---|---|
| `a`, `b` | yes | none | Different node names from `nodes` |
| `bandwidth_mbps` | yes | none | Above 0 |
| `delay_ms` | yes | none | 0 or more. Propagation delay. |
| `loss_prob` | no | `0.0` | At least 0, below 1. Independent per packet, applied after transmission. |
| `queue` | no | drop-tail, capacity 100 | See below |

## Queue

| Key | Default | Rules |
|---|---|---|
| `type` | `droptail` | `droptail` or `red` |
| `capacity` | `100` | Integer, 1 or more |
| `min_threshold`, `max_threshold` | 25% and 75% of capacity | `red` only. `0 < min < max <= capacity`. Rejected for `droptail`. |
| `max_p` | `0.1` | Above 0, at most 1. Used by `red`. |
| `weight` | `0.002` | Above 0, at most 1. Averaging weight for `red`. |

## Flow

| Key | Required | Default | Rules |
|---|---|---|---|
| `id` | yes | none | Non-empty, unique |
| `src`, `dst` | yes | none | Different node names. There must be a route between them. |
| `kind` | yes | none | `tcp`, `cbr` or `poisson` |
| `start` | no | `0` | At least 0 and below `duration` |
| `stop` | no | `duration` | Above `start`, at most `duration`. No new data is sent after it. |
| `packet_size` | no | `1000` | Integer, 64 or more |
| `cc` | no | `aimd` | `fixed`, `aimd` or `cubic`. **`tcp` only**: writing the key on another kind is an error. |
| `window` | no | `10` | 1 or more. Only valid together with `cc: fixed`. |
| `rate_mbps` | cbr, poisson | none | Above 0. Not allowed on `tcp`. |
| `packets` | no | unlimited | Integer, 1 or more. Finite transfer size, `tcp` only. |

Routes are hop-count shortest paths with ties broken alphabetically, so a scenario always produces the same routes.

## Example

```yaml
seed: 7
duration: 20
nodes: [a, r, b]
links:
  - {a: a, b: r, bandwidth_mbps: 100, delay_ms: 2}
  - a: r
    b: b
    bandwidth_mbps: 10
    delay_ms: 20
    queue: {type: red, capacity: 60}
flows:
  - {id: bulk, src: a, dst: b, kind: tcp, cc: cubic}
  - {id: voice, src: a, dst: b, kind: cbr, rate_mbps: 1, start: 2}
```
