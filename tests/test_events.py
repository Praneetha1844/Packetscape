from __future__ import annotations

import pytest

from packetscape.events import Scheduler


def test_events_run_in_time_order() -> None:
    sched = Scheduler()
    order: list[str] = []
    sched.schedule(2.0, lambda: order.append("late"))
    sched.schedule(1.0, lambda: order.append("early"))
    sched.run(until=5.0)
    assert order == ["early", "late"]


def test_simultaneous_events_keep_insertion_order() -> None:
    sched = Scheduler()
    order: list[int] = []
    for i in range(5):
        sched.schedule(1.0, lambda i=i: order.append(i))
    sched.run(until=1.0)
    assert order == [0, 1, 2, 3, 4]


def test_clock_advances_to_until_and_future_events_wait() -> None:
    sched = Scheduler()
    fired: list[float] = []
    sched.schedule(10.0, lambda: fired.append(sched.now))
    assert sched.run(until=5.0) == 0
    assert sched.now == 5.0
    assert sched.run(until=10.0) == 1
    assert fired == [10.0]


def test_cancelled_events_do_not_run() -> None:
    sched = Scheduler()
    fired: list[int] = []
    handle = sched.schedule(1.0, lambda: fired.append(1))
    handle.cancel()
    assert handle.cancelled
    sched.run(until=2.0)
    assert fired == []
    assert sched.processed == 0


def test_events_can_schedule_further_events() -> None:
    sched = Scheduler()
    times: list[float] = []

    def tick() -> None:
        times.append(sched.now)
        if len(times) < 3:
            sched.schedule(1.0, tick)

    sched.schedule(0.0, tick)
    sched.run(until=10.0)
    assert times == [0.0, 1.0, 2.0]


@pytest.mark.parametrize("delay", [-1.0, float("nan")])
def test_invalid_delay_is_rejected(delay: float) -> None:
    with pytest.raises(ValueError):
        Scheduler().schedule(delay, lambda: None)


def test_running_backwards_is_rejected() -> None:
    sched = Scheduler()
    sched.run(until=5.0)
    with pytest.raises(ValueError):
        sched.run(until=1.0)
