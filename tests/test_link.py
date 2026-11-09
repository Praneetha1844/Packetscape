from __future__ import annotations

import random

import pytest
from conftest import FixedRandom

from packetscape.events import Scheduler
from packetscape.metrics import MetricsCollector
from packetscape.network import Link
from packetscape.packet import Packet
from packetscape.queues import DropTailQueue


def build(
    *, capacity: int = 10, loss_prob: float = 0.0, rng: random.Random | None = None
) -> tuple[Scheduler, MetricsCollector, Link, list[tuple[float, int]]]:
    sched = Scheduler()
    metrics = MetricsCollector()
    metrics.register_flow("f", "cbr", start=0.0)
    arrivals: list[tuple[float, int]] = []
    link = Link(
        scheduler=sched,
        metrics=metrics,
        queue=DropTailQueue(capacity),
        bandwidth_bps=1e6,
        delay_s=0.010,
        loss_prob=loss_prob,
        rng=rng or random.Random(0),
        on_arrival=lambda p: arrivals.append((sched.now, p.seq)),
    )
    return sched, metrics, link, arrivals


def packet(seq: int) -> Packet:
    return Packet("f", seq, 1000, 0.0, ("a", "b"))


def test_single_packet_arrives_after_serialization_plus_propagation() -> None:
    sched, _, link, arrivals = build()
    link.send(packet(0))
    sched.run(until=1.0)
    # 1000 B * 8 / 1 Mb/s = 8 ms transmit, plus 10 ms propagation.
    assert arrivals == [(pytest.approx(0.018), 0)]


def test_back_to_back_packets_are_serialized_one_at_a_time() -> None:
    sched, _, link, arrivals = build()
    link.send(packet(0))
    link.send(packet(1))
    sched.run(until=1.0)
    assert [seq for _, seq in arrivals] == [0, 1]
    assert arrivals[0][0] == pytest.approx(0.018)
    assert arrivals[1][0] == pytest.approx(0.026)


def test_queue_overflow_is_recorded_as_queue_drop() -> None:
    sched, metrics, link, arrivals = build(capacity=1)
    for seq in range(3):
        link.send(packet(seq))  # first goes straight to the wire, second queues, third drops
    sched.run(until=1.0)
    assert [seq for _, seq in arrivals] == [0, 1]
    assert metrics.stats("f").dropped_queue == 1


def test_random_loss_drops_packet_after_transmission() -> None:
    sched, metrics, link, arrivals = build(loss_prob=0.5, rng=FixedRandom(0.0))
    link.send(packet(0))
    sched.run(until=1.0)
    assert arrivals == []
    assert metrics.stats("f").dropped_loss == 1


def test_loss_is_not_applied_when_draw_is_above_probability() -> None:
    sched, metrics, link, arrivals = build(loss_prob=0.5, rng=FixedRandom(0.9))
    link.send(packet(0))
    sched.run(until=1.0)
    assert len(arrivals) == 1
    assert metrics.stats("f").dropped_loss == 0
