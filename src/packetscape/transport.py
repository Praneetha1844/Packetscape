"""Traffic sources and a simplified TCP-like transport.

* ``UdpSource`` emits packets open-loop, either at a constant bit rate or as a
  Poisson process.
* ``TcpSender`` / ``TcpReceiver`` implement a packet-granular, cumulative-ACK
  reliable transport driven by a pluggable :class:`CongestionControl`.
"""

from __future__ import annotations

import random
from functools import partial

from packetscape.congestion import CongestionControl
from packetscape.events import EventHandle, Scheduler
from packetscape.metrics import MetricsCollector
from packetscape.network import Network
from packetscape.packet import ACK_SIZE_BYTES, Packet

MIN_RTO = 0.2
MAX_RTO = 60.0
INITIAL_RTO = 1.0
DUPACK_THRESHOLD = 3


class UdpSource:
    """Open-loop traffic source (``cbr`` or ``poisson`` inter-departure times)."""

    def __init__(
        self,
        *,
        flow_id: str,
        path: tuple[str, ...],
        packet_size: int,
        rate_bps: float,
        pattern: str,
        start: float,
        stop: float,
        scheduler: Scheduler,
        network: Network,
        metrics: MetricsCollector,
        rng: random.Random,
    ) -> None:
        if rate_bps <= 0:
            raise ValueError("rate_bps must be positive")
        if pattern not in ("cbr", "poisson"):
            raise ValueError(f"unknown pattern {pattern!r}")
        self._flow_id = flow_id
        self._path = path
        self._packet_size = packet_size
        self._packets_per_second = rate_bps / (8.0 * packet_size)
        self._pattern = pattern
        self._start = start
        self._stop = stop
        self._scheduler = scheduler
        self._network = network
        self._metrics = metrics
        self._rng = rng
        self._seq = 0

    def start(self) -> None:
        self._scheduler.schedule(self._start - self._scheduler.now, self._emit)

    def _next_gap(self) -> float:
        if self._pattern == "cbr":
            return 1.0 / self._packets_per_second
        return self._rng.expovariate(self._packets_per_second)

    def _emit(self) -> None:
        now = self._scheduler.now
        if now >= self._stop:
            return
        packet = Packet(self._flow_id, self._seq, self._packet_size, now, self._path)
        self._seq += 1
        self._metrics.record_sent(packet)
        self._network.inject(packet)
        self._scheduler.schedule(self._next_gap(), self._emit)


class UdpSink:
    """Destination for open-loop flows: records every arrival."""

    def __init__(self, scheduler: Scheduler, metrics: MetricsCollector) -> None:
        self._scheduler = scheduler
        self._metrics = metrics

    def on_data(self, packet: Packet) -> None:
        self._metrics.record_delivery(packet, self._scheduler.now)


class TcpReceiver:
    """Cumulative-ACK receiver that buffers out-of-order packets."""

    def __init__(
        self,
        *,
        flow_id: str,
        reverse_path: tuple[str, ...],
        scheduler: Scheduler,
        network: Network,
        metrics: MetricsCollector,
    ) -> None:
        self._flow_id = flow_id
        self._reverse_path = reverse_path
        self._scheduler = scheduler
        self._network = network
        self._metrics = metrics
        self._expected = 0
        self._buffer: set[int] = set()

    def on_data(self, packet: Packet) -> None:
        now = self._scheduler.now
        is_new = packet.seq >= self._expected and packet.seq not in self._buffer
        if is_new:
            self._metrics.record_delivery(packet, now)
            if packet.seq == self._expected:
                self._expected += 1
                while self._expected in self._buffer:
                    self._buffer.remove(self._expected)
                    self._expected += 1
            else:
                self._buffer.add(packet.seq)
        ack = Packet(
            self._flow_id,
            0,
            ACK_SIZE_BYTES,
            now,
            self._reverse_path,
            is_ack=True,
            ack_no=self._expected,
        )
        self._network.inject(ack)


class TcpSender:
    """Packet-granular sender: sliding window, fast retransmit and RTO."""

    def __init__(
        self,
        *,
        flow_id: str,
        path: tuple[str, ...],
        packet_size: int,
        cc: CongestionControl,
        start: float,
        stop: float,
        total_packets: int | None,
        scheduler: Scheduler,
        network: Network,
        metrics: MetricsCollector,
    ) -> None:
        self._flow_id = flow_id
        self._path = path
        self._packet_size = packet_size
        self._cc = cc
        self._start = start
        self._stop = stop
        self._total = total_packets
        self._scheduler = scheduler
        self._network = network
        self._metrics = metrics

        self._next_seq = 0
        self._snd_una = 0
        self._dupacks = 0
        self._recover = 0
        self._send_times: dict[int, float] = {}
        self._srtt: float | None = None
        self._rttvar = 0.0
        self._rto = INITIAL_RTO
        self._timer: EventHandle | None = None

    @property
    def inflight(self) -> int:
        return self._next_seq - self._snd_una

    def start(self) -> None:
        self._scheduler.schedule(self._start - self._scheduler.now, self._begin)

    def _begin(self) -> None:
        self._trace()
        self._try_send()

    def _trace(self) -> None:
        self._metrics.record_cwnd(self._flow_id, self._scheduler.now, self._cc.cwnd)

    def _try_send(self) -> None:
        if self._scheduler.now >= self._stop:
            return
        window = max(1, int(self._cc.cwnd))
        while self.inflight < window and (self._total is None or self._next_seq < self._total):
            self._transmit(self._next_seq, retransmit=False)
            self._next_seq += 1

    def _transmit(self, seq: int, *, retransmit: bool) -> None:
        now = self._scheduler.now
        if retransmit:
            self._send_times.pop(seq, None)  # Karn's rule: never sample RTT from a retransmit
        else:
            self._send_times[seq] = now
        packet = Packet(self._flow_id, seq, self._packet_size, now, self._path)
        self._metrics.record_sent(packet)
        if self._timer is None:
            self._arm_timer()
        self._network.inject(packet)

    def _arm_timer(self) -> None:
        self._cancel_timer()
        self._timer = self._scheduler.schedule(self._rto, partial(self._on_timeout))

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _update_rto(self, rtt: float) -> None:
        """RFC 6298 smoothing with clamped bounds."""
        if self._srtt is None:
            self._srtt = rtt
            self._rttvar = rtt / 2.0
        else:
            self._rttvar = 0.75 * self._rttvar + 0.25 * abs(self._srtt - rtt)
            self._srtt = 0.875 * self._srtt + 0.125 * rtt
        self._rto = min(MAX_RTO, max(MIN_RTO, self._srtt + max(0.01, 4.0 * self._rttvar)))

    def _on_timeout(self) -> None:
        self._timer = None
        if self.inflight == 0:
            return
        self._cc.on_timeout(self._scheduler.now)
        self._trace()
        self._rto = min(MAX_RTO, self._rto * 2.0)
        self._recover = self._next_seq
        self._dupacks = 0
        self._send_times.clear()
        self._transmit(self._snd_una, retransmit=True)

    def on_ack(self, packet: Packet) -> None:
        ack = packet.ack_no
        now = self._scheduler.now
        if ack > self._next_seq:
            return  # acknowledges data never sent; ignore
        if ack > self._snd_una:
            newly = ack - self._snd_una
            sent_at = self._send_times.get(ack - 1)
            rtt = now - sent_at if sent_at is not None else None
            if rtt is not None:
                self._update_rto(rtt)
            for seq in range(self._snd_una, ack):
                self._send_times.pop(seq, None)
            self._snd_una = ack
            self._dupacks = 0
            self._cc.on_ack(newly, rtt, now)
            self._trace()
            if self.inflight > 0:
                self._arm_timer()
            else:
                self._cancel_timer()
            self._try_send()
        elif ack == self._snd_una and self.inflight > 0:
            self._dupacks += 1
            if self._dupacks == DUPACK_THRESHOLD and self._snd_una >= self._recover:
                self._cc.on_fast_retransmit(now)
                self._trace()
                self._recover = self._next_seq
                self._transmit(self._snd_una, retransmit=True)
