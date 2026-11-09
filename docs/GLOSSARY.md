# Glossary

| Term | Meaning |
|---|---|
| **Discrete-event simulation** | State changes only at events kept in a time-ordered queue; the clock jumps from event to event. |
| **Scheduler** | The min-heap of pending events. Ties are broken by insertion order. |
| **Link** | One direction of a physical link: an output queue, a serializer and a propagation delay. |
| **Serialization delay** | Time to put a packet on the wire: size times 8 divided by bandwidth. |
| **Propagation delay** | Time for a bit to cross the link, independent of packet size. |
| **Drop-tail** | A FIFO queue that drops arrivals when full. |
| **RED** | Random Early Detection: drops arrivals with rising probability as the average queue grows. |
| **cwnd** | Congestion window: how many packets the sender may have unacknowledged. |
| **ssthresh** | Slow-start threshold: below it the window grows by one per ACK, above it by about one per round trip. |
| **AIMD** | Additive increase, multiplicative decrease. |
| **Fast retransmit** | Resending the oldest unacknowledged packet after three duplicate ACKs. |
| **RTO** | Retransmission timeout, computed from smoothed round-trip samples (RFC 6298 style). |
| **Karn's rule** | Never take an RTT sample from a retransmitted packet. |
| **Goodput** | Unique data delivered per unit time; retransmitted duplicates are not counted. |
| **Jain's fairness index** | `(sum x)^2 / (n * sum x^2)`: 1 means equal shares, `1/n` means one flow takes everything. |
| **Percentile (nearest rank)** | The value at rank `ceil(p/100 * n)` in the sorted samples. |
| **Seed** | Integer that fixes every random choice in a run. |
