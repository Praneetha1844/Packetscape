# Model assumptions and limits

Packetscape trades fidelity for readability. Treat results as qualitative comparisons between policies under the same simplified model, not as predictions of real network behaviour.

## What is modelled

- Links: serialization delay (`size * 8 / bandwidth`), constant propagation delay, independent random loss per packet, one output queue per direction.
- Queues: drop-tail FIFO and RED with a packet-count capacity.
- Transport: sliding window in whole packets, cumulative ACKs, out-of-order buffering at the receiver, fast retransmit after three duplicate ACKs, retransmission timeout with exponential backoff, Karn's rule for RTT samples.
- Traffic: bulk TCP-like transfers, constant bit rate and Poisson sources.

## What is not modelled

| Not modelled | Consequence |
|---|---|
| Byte streams, MSS negotiation | Windows and sequence numbers count packets |
| Selective acknowledgements, delayed ACKs | Recovery from several losses in one window is slower than in modern stacks |
| Connection setup and teardown | Flows start sending immediately |
| Receiver window / flow control | Only the congestion window limits the sender |
| ECN, BBR, hybrid slow start | Absent; CUBIC is a simplified curve |
| Routing protocols, link failures | Routes are static hop-count shortest paths |
| Byte-limited queues, per-flow queueing | Queue limits are packet counts |
| Processing delay, cross-layer effects | Nodes forward instantly |
| Wireless, MAC contention | Links are point-to-point and error-free except for the configured loss |

## Semantics worth knowing

- **Throughput** counts each sequence number once, when it first reaches the destination, over the window from the flow's start to the end of the run. It is goodput of unique data, so retransmissions do not inflate it.
- **Loss ratio** is `(queue drops + random drops) / packets sent`, where retransmissions count as sent packets.
- **Delay** is one-way, from the creation of the transmitted copy of a packet to its first arrival.
- **Jain's index** is computed over the throughput of all flows in the scenario, including open-loop ones. If every flow has zero throughput it is reported as 1.0.
- **ACK drops** are counted in a single counter and excluded from per-flow loss figures.
- **RED** omits the idle-time correction of the original algorithm.
- **Initial window** is 2 packets and the initial slow-start threshold is effectively unbounded.

## Validity guidance

- Compare policies using the same scenario file and seed, and prefer several seeds before drawing conclusions. A multi-seed runner is on the roadmap.
- Very small queues, very short runs or very high loss rates can make the simplified recovery logic dominate the outcome.
- Do not quote numbers without the command and seed that produced them.
