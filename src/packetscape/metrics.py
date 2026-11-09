"""Metric collection and summary statistics.

Throughput is *goodput of unique data packets*: each sequence number is counted
once when it first reaches the destination, so retransmitted duplicates do not
inflate the figure. The measurement window of a flow runs from its start time
to the end of the simulation.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from packetscape.packet import Packet


def percentile(values: Sequence[float], pct: float) -> float:
    """Nearest-rank percentile (``pct`` in (0, 100])."""
    if not values:
        raise ValueError("percentile of an empty sequence is undefined")
    if not 0 < pct <= 100:
        raise ValueError("pct must be in (0, 100]")
    ordered = sorted(values)
    rank = math.ceil(pct / 100.0 * len(ordered))
    return ordered[max(rank, 1) - 1]


def jain_index(values: Sequence[float]) -> float:
    """Jain's fairness index: ``(sum x)^2 / (n * sum x^2)``, between ``1/n`` and 1.

    When every value is zero the allocation is trivially equal and 1.0 is returned.
    """
    if not values:
        raise ValueError("jain_index of an empty sequence is undefined")
    if any(v < 0 for v in values):
        raise ValueError("values must be non-negative")
    squares = sum(v * v for v in values)
    if squares == 0:
        return 1.0
    total = sum(values)
    return (total * total) / (len(values) * squares)


@dataclass
class FlowStats:
    """Mutable counters for one flow."""

    flow_id: str
    kind: str
    start: float
    sent_packets: int = 0
    sent_bytes: int = 0
    delivered_packets: int = 0
    delivered_bytes: int = 0
    dropped_queue: int = 0
    dropped_loss: int = 0
    delays: list[float] = field(default_factory=list)
    cwnd_trace: list[tuple[float, float]] = field(default_factory=list)


@dataclass(frozen=True)
class FlowSummary:
    """Immutable per-flow results."""

    flow_id: str
    kind: str
    sent_packets: int
    delivered_packets: int
    delivered_bytes: int
    dropped_queue: int
    dropped_loss: int
    throughput_bps: float
    loss_ratio: float
    delay_mean_ms: float | None
    delay_p50_ms: float | None
    delay_p95_ms: float | None
    delay_p99_ms: float | None


class MetricsCollector:
    """Receives events from links and transports and builds summaries."""

    def __init__(self) -> None:
        self._flows: dict[str, FlowStats] = {}
        self.ack_drops = 0

    def register_flow(self, flow_id: str, kind: str, start: float) -> None:
        if flow_id in self._flows:
            raise ValueError(f"flow {flow_id!r} already registered")
        self._flows[flow_id] = FlowStats(flow_id=flow_id, kind=kind, start=start)

    def stats(self, flow_id: str) -> FlowStats:
        return self._flows[flow_id]

    def record_sent(self, packet: Packet) -> None:
        stats = self._flows[packet.flow_id]
        stats.sent_packets += 1
        stats.sent_bytes += packet.size_bytes

    def record_drop(self, packet: Packet, reason: str) -> None:
        """Record a drop. ``reason`` is ``"queue"`` or ``"loss"``. ACK drops are tallied apart."""
        if packet.is_ack:
            self.ack_drops += 1
            return
        stats = self._flows[packet.flow_id]
        if reason == "queue":
            stats.dropped_queue += 1
        elif reason == "loss":
            stats.dropped_loss += 1
        else:
            raise ValueError(f"unknown drop reason {reason!r}")

    def record_delivery(self, packet: Packet, now: float) -> None:
        """Record the first arrival of a data packet at its destination."""
        stats = self._flows[packet.flow_id]
        stats.delivered_packets += 1
        stats.delivered_bytes += packet.size_bytes
        stats.delays.append(now - packet.created_at)

    def record_cwnd(self, flow_id: str, now: float, cwnd: float) -> None:
        trace = self._flows[flow_id].cwnd_trace
        if not trace or trace[-1][1] != cwnd:
            trace.append((now, cwnd))

    def summarize(self, duration: float) -> list[FlowSummary]:
        """Summaries in flow-registration order."""
        return [self._summarize(stats, duration) for stats in self._flows.values()]

    @staticmethod
    def _summarize(stats: FlowStats, duration: float) -> FlowSummary:
        window = duration - stats.start
        throughput = stats.delivered_bytes * 8.0 / window if window > 0 else 0.0
        dropped = stats.dropped_queue + stats.dropped_loss
        loss_ratio = dropped / stats.sent_packets if stats.sent_packets else 0.0
        delays = stats.delays
        has = bool(delays)
        return FlowSummary(
            flow_id=stats.flow_id,
            kind=stats.kind,
            sent_packets=stats.sent_packets,
            delivered_packets=stats.delivered_packets,
            delivered_bytes=stats.delivered_bytes,
            dropped_queue=stats.dropped_queue,
            dropped_loss=stats.dropped_loss,
            throughput_bps=throughput,
            loss_ratio=loss_ratio,
            delay_mean_ms=(sum(delays) / len(delays)) * 1000.0 if has else None,
            delay_p50_ms=percentile(delays, 50) * 1000.0 if has else None,
            delay_p95_ms=percentile(delays, 95) * 1000.0 if has else None,
            delay_p99_ms=percentile(delays, 99) * 1000.0 if has else None,
        )
