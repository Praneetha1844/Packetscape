# ADR 0003: A simplified, packet-granular transport

- Status: accepted
- Date: 2026-11-09

## Context

The goal is to compare congestion-control and queueing policies while keeping every moving part readable. A faithful TCP implementation (byte sequence numbers, SACK, delayed ACKs, handshake, receive window, timestamps) would multiply the code and make the effect of a policy harder to isolate.

## Decision

Model the transport at packet granularity:

- Sequence and acknowledgement numbers count whole packets.
- The receiver sends one cumulative ACK per data packet and buffers out-of-order arrivals.
- The sender recovers with fast retransmit (three duplicate ACKs, at most once per recovery window) and a retransmission timer using RFC 6298 smoothing, exponential backoff and Karn's rule.
- Congestion controllers implement three callbacks (`on_ack`, `on_fast_retransmit`, `on_timeout`) and own `cwnd` and `ssthresh`.
- CUBIC is implemented as its window curve only, labelled `CubicLite`; the TCP-friendly region and fast convergence are left out.

## Consequences

- A new controller is a few dozen lines and does not touch the sender.
- Behaviour after multiple losses within a window is cruder than in real stacks because there is no SACK; this is documented in [model-and-limits](../model-and-limits.md) and affects absolute numbers more than relative comparisons.
- No connection setup means the first window starts at once, so short flows look better than they would in reality.
- Results should be described as comparisons within this model. Claims about real deployments would need a more faithful simulator or measurements.
