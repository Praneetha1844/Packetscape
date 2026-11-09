from __future__ import annotations

import random

import pytest
from conftest import FixedRandom

from packetscape.packet import Packet
from packetscape.queues import DropTailQueue, RedQueue


def make_packet(seq: int = 0) -> Packet:
    return Packet("f", seq, 1000, 0.0, ("a", "b"))


def test_droptail_is_fifo() -> None:
    queue = DropTailQueue(3)
    for seq in range(3):
        assert queue.enqueue(make_packet(seq), 0.0)
    order = []
    for _ in range(3):
        packet = queue.dequeue(0.0)
        assert packet is not None
        order.append(packet.seq)
    assert order == [0, 1, 2]
    assert queue.dequeue(0.0) is None


def test_droptail_drops_when_full() -> None:
    queue = DropTailQueue(2)
    assert queue.enqueue(make_packet(0), 0.0)
    assert queue.enqueue(make_packet(1), 0.0)
    assert not queue.enqueue(make_packet(2), 0.0)
    assert len(queue) == 2


def test_droptail_rejects_zero_capacity() -> None:
    with pytest.raises(ValueError):
        DropTailQueue(0)


def make_red(rng: random.Random) -> RedQueue:
    return RedQueue(capacity=10, min_threshold=2, max_threshold=5, max_p=0.1, weight=1.0, rng=rng)


def test_red_accepts_below_min_threshold() -> None:
    queue = make_red(FixedRandom(0.0))
    assert queue.enqueue(make_packet(0), 0.0)
    assert queue.enqueue(make_packet(1), 0.0)


def test_red_drops_everything_at_or_above_max_threshold() -> None:
    queue = make_red(FixedRandom(0.999))
    results = [queue.enqueue(make_packet(i), 0.0) for i in range(6)]
    assert results == [True, True, True, True, True, False]


def test_red_drops_probabilistically_between_thresholds() -> None:
    # With weight=1 the average equals the instantaneous length. A draw of 0.0
    # is below any positive drop probability, so the first arrival that sees a
    # positive probability (queue length 3) is dropped.
    queue = make_red(FixedRandom(0.0))
    results = [queue.enqueue(make_packet(i), 0.0) for i in range(4)]
    assert results == [True, True, True, False]


@pytest.mark.parametrize(
    "override",
    [
        {"min_threshold": 5, "max_threshold": 2},
        {"min_threshold": 0},
        {"max_threshold": 50},
        {"max_p": 0.0},
        {"weight": 1.5},
    ],
)
def test_red_rejects_invalid_parameters(override: dict[str, float]) -> None:
    params = {"min_threshold": 2.0, "max_threshold": 5.0, "max_p": 0.1, "weight": 0.5}
    params.update(override)
    with pytest.raises(ValueError):
        RedQueue(
            capacity=10,
            min_threshold=params["min_threshold"],
            max_threshold=params["max_threshold"],
            max_p=params["max_p"],
            weight=params["weight"],
            rng=random.Random(0),
        )
