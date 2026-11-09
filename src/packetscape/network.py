"""Links and packet forwarding.

A :class:`Link` is one *direction* of a physical link: an output queue, a
serializer that transmits one packet at a time at the link bandwidth, and a
propagation delay with optional random loss. :class:`Network` wires links
together and delivers packets to registered endpoints.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from functools import partial

from packetscape.events import Scheduler
from packetscape.metrics import MetricsCollector
from packetscape.packet import Packet
from packetscape.queues import QueueDiscipline

Handler = Callable[[Packet], None]


class Link:
    """One direction of a link."""

    def __init__(
        self,
        scheduler: Scheduler,
        metrics: MetricsCollector,
        queue: QueueDiscipline,
        bandwidth_bps: float,
        delay_s: float,
        loss_prob: float,
        rng: random.Random,
        on_arrival: Handler,
    ) -> None:
        self._scheduler = scheduler
        self._metrics = metrics
        self._queue = queue
        self._bandwidth_bps = bandwidth_bps
        self._delay_s = delay_s
        self._loss_prob = loss_prob
        self._rng = rng
        self._on_arrival = on_arrival
        self._busy = False

    @property
    def queue_length(self) -> int:
        return len(self._queue)

    def send(self, packet: Packet) -> None:
        """Offer a packet to the output queue; start transmitting if the link is idle."""
        if not self._queue.enqueue(packet, self._scheduler.now):
            self._metrics.record_drop(packet, "queue")
            return
        if not self._busy:
            self._start_transmission()

    def _start_transmission(self) -> None:
        packet = self._queue.dequeue(self._scheduler.now)
        if packet is None:
            self._busy = False
            return
        self._busy = True
        transmit_time = packet.size_bytes * 8.0 / self._bandwidth_bps
        self._scheduler.schedule(transmit_time, partial(self._finish_transmission, packet))

    def _finish_transmission(self, packet: Packet) -> None:
        self._scheduler.schedule(self._delay_s, partial(self._arrive, packet))
        self._start_transmission()

    def _arrive(self, packet: Packet) -> None:
        if self._loss_prob > 0.0 and self._rng.random() < self._loss_prob:
            self._metrics.record_drop(packet, "loss")
            return
        self._on_arrival(packet)


class Network:
    """Connects links and dispatches packets that reach their destination."""

    def __init__(self) -> None:
        self._links: dict[tuple[str, str], Link] = {}
        self._endpoints: dict[tuple[str, bool], Handler] = {}

    def add_link(self, src: str, dst: str, link: Link) -> None:
        if (src, dst) in self._links:
            raise ValueError(f"link {src}->{dst} already exists")
        self._links[(src, dst)] = link

    def link(self, src: str, dst: str) -> Link:
        return self._links[(src, dst)]

    def register(self, flow_id: str, is_ack: bool, handler: Handler) -> None:
        """Register the handler for data (or ACK) packets of a flow at its endpoint."""
        key = (flow_id, is_ack)
        if key in self._endpoints:
            raise ValueError(f"endpoint for {key} already registered")
        self._endpoints[key] = handler

    def inject(self, packet: Packet) -> None:
        """Hand a packet to the network at ``packet.path[packet.hop]``."""
        self.forward(packet)

    def on_link_arrival(self, packet: Packet) -> None:
        """Called by a link when a packet reaches the next node."""
        packet.hop += 1
        self.forward(packet)

    def forward(self, packet: Packet) -> None:
        if packet.hop == len(packet.path) - 1:
            handler = self._endpoints.get((packet.flow_id, packet.is_ack))
            if handler is None:
                raise KeyError(f"no endpoint registered for flow {packet.flow_id!r}")
            handler(packet)
            return
        link = self._links[(packet.path[packet.hop], packet.path[packet.hop + 1])]
        link.send(packet)
