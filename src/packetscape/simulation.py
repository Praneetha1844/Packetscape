"""Scenario assembly and execution."""

from __future__ import annotations

import random
from dataclasses import dataclass

from packetscape.config import FlowConfig, QueueConfig, SimConfig
from packetscape.congestion import make_congestion_control
from packetscape.events import Scheduler
from packetscape.metrics import FlowSummary, MetricsCollector, jain_index
from packetscape.network import Link, Network
from packetscape.queues import DropTailQueue, QueueDiscipline, RedQueue
from packetscape.topology import LinkSpec, Topology
from packetscape.transport import TcpReceiver, TcpSender, UdpSink, UdpSource


def child_rng(seed: int, name: str) -> random.Random:
    """Independent RNG stream per component.

    Seeding from a string is deterministic across interpreter runs (it does not
    depend on ``PYTHONHASHSEED``), and giving every component its own stream
    means adding a flow does not reshuffle the random draws of existing ones.
    """
    return random.Random(f"{seed}/{name}")


@dataclass(frozen=True)
class SimulationResult:
    """Everything produced by one run."""

    name: str
    seed: int
    duration: float
    events: int
    flows: tuple[FlowSummary, ...]
    jain_index: float
    ack_drops: int
    cwnd_traces: dict[str, list[tuple[float, float]]]


def make_queue(config: QueueConfig, rng: random.Random) -> QueueDiscipline:
    """Instantiate the queue discipline described by ``config``."""
    if config.type == "droptail":
        return DropTailQueue(config.capacity)
    if config.type == "red":
        if config.min_threshold is None or config.max_threshold is None:
            raise ValueError("red queue requires min_threshold and max_threshold")
        return RedQueue(
            capacity=config.capacity,
            min_threshold=config.min_threshold,
            max_threshold=config.max_threshold,
            max_p=config.max_p,
            weight=config.weight,
            rng=rng,
        )
    raise ValueError(f"unknown queue type {config.type!r}")


class Simulation:
    """Builds the network and traffic for a scenario and runs it to completion."""

    def __init__(self, config: SimConfig) -> None:
        self._config = config
        self._scheduler = Scheduler()
        self._metrics = MetricsCollector()
        self._network = Network()
        self._ran = False

        specs = [
            LinkSpec(
                link.a,
                link.b,
                link.bandwidth_mbps * 1e6,
                link.delay_ms / 1000.0,
                link.loss_prob,
            )
            for link in config.links
        ]
        self._topology = Topology(list(config.nodes), specs)
        self._build_links()
        self._build_flows()

    def _build_links(self) -> None:
        seed = self._config.seed
        for link in self._config.links:
            for src, dst in ((link.a, link.b), (link.b, link.a)):
                self._network.add_link(
                    src,
                    dst,
                    Link(
                        scheduler=self._scheduler,
                        metrics=self._metrics,
                        queue=make_queue(link.queue, child_rng(seed, f"queue/{src}->{dst}")),
                        bandwidth_bps=link.bandwidth_mbps * 1e6,
                        delay_s=link.delay_ms / 1000.0,
                        loss_prob=link.loss_prob,
                        rng=child_rng(seed, f"link/{src}->{dst}"),
                        on_arrival=self._network.on_link_arrival,
                    ),
                )

    def _build_flows(self) -> None:
        for flow in self._config.flows:
            path = self._topology.shortest_path(flow.src, flow.dst)
            self._metrics.register_flow(flow.id, flow.kind, flow.start)
            if flow.kind == "tcp":
                self._build_tcp(flow, path)
            else:
                self._build_udp(flow, path)

    def _build_tcp(self, flow: FlowConfig, path: tuple[str, ...]) -> None:
        stop = flow.stop if flow.stop is not None else self._config.duration
        receiver = TcpReceiver(
            flow_id=flow.id,
            reverse_path=tuple(reversed(path)),
            scheduler=self._scheduler,
            network=self._network,
            metrics=self._metrics,
        )
        sender = TcpSender(
            flow_id=flow.id,
            path=path,
            packet_size=flow.packet_size,
            cc=make_congestion_control(flow.cc, flow.window),
            start=flow.start,
            stop=stop,
            total_packets=flow.packets,
            scheduler=self._scheduler,
            network=self._network,
            metrics=self._metrics,
        )
        self._network.register(flow.id, False, receiver.on_data)
        self._network.register(flow.id, True, sender.on_ack)
        sender.start()

    def _build_udp(self, flow: FlowConfig, path: tuple[str, ...]) -> None:
        if flow.rate_mbps is None:
            raise ValueError(f"flow {flow.id!r} requires rate_mbps")
        stop = flow.stop if flow.stop is not None else self._config.duration
        sink = UdpSink(self._scheduler, self._metrics)
        source = UdpSource(
            flow_id=flow.id,
            path=path,
            packet_size=flow.packet_size,
            rate_bps=flow.rate_mbps * 1e6,
            pattern=flow.kind,
            start=flow.start,
            stop=stop,
            scheduler=self._scheduler,
            network=self._network,
            metrics=self._metrics,
            rng=child_rng(self._config.seed, f"source/{flow.id}"),
        )
        self._network.register(flow.id, False, sink.on_data)
        source.start()

    def run(self) -> SimulationResult:
        """Run the scenario once. A :class:`Simulation` cannot be re-run."""
        if self._ran:
            raise RuntimeError("simulation already ran; build a new Simulation")
        self._ran = True
        executed = self._scheduler.run(self._config.duration)
        summaries = tuple(self._metrics.summarize(self._config.duration))
        return SimulationResult(
            name=self._config.name,
            seed=self._config.seed,
            duration=self._config.duration,
            events=executed,
            flows=summaries,
            jain_index=jain_index([s.throughput_bps for s in summaries]),
            ack_drops=self._metrics.ack_drops,
            cwnd_traces={
                s.flow_id: list(self._metrics.stats(s.flow_id).cwnd_trace)
                for s in summaries
                if s.kind == "tcp"
            },
        )
