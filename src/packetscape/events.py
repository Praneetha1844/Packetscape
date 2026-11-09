"""Deterministic discrete-event scheduler.

Events are ordered by ``(time, insertion counter)``. The counter makes ordering
of simultaneous events stable, which is what keeps whole simulations
reproducible for a given seed.
"""

from __future__ import annotations

import heapq
import itertools
from collections.abc import Callable
from dataclasses import dataclass, field

Action = Callable[[], None]


@dataclass(order=True)
class _Entry:
    time: float
    seq: int
    action: Action = field(compare=False)
    cancelled: bool = field(default=False, compare=False)


class EventHandle:
    """Handle returned by :meth:`Scheduler.schedule`; allows cancellation."""

    __slots__ = ("_entry",)

    def __init__(self, entry: _Entry) -> None:
        self._entry = entry

    def cancel(self) -> None:
        """Mark the event as cancelled. A cancelled event is skipped when due."""
        self._entry.cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._entry.cancelled


class Scheduler:
    """A min-heap event queue with a monotonically advancing clock."""

    def __init__(self) -> None:
        self._heap: list[_Entry] = []
        self._counter = itertools.count()
        self._now = 0.0
        self._processed = 0

    @property
    def now(self) -> float:
        """Current simulation time in seconds."""
        return self._now

    @property
    def processed(self) -> int:
        """Number of events executed so far (cancelled events excluded)."""
        return self._processed

    def schedule(self, delay: float, action: Action) -> EventHandle:
        """Run ``action`` after ``delay`` seconds of simulated time."""
        if not delay >= 0.0:  # also rejects NaN
            raise ValueError(f"delay must be >= 0, got {delay!r}")
        entry = _Entry(self._now + delay, next(self._counter), action)
        heapq.heappush(self._heap, entry)
        return EventHandle(entry)

    def run(self, until: float) -> int:
        """Execute events with ``time <= until`` and advance the clock to ``until``.

        Returns the number of events executed in this call.
        """
        if not until >= self._now:
            raise ValueError(f"until ({until!r}) is earlier than now ({self._now!r})")
        executed = 0
        while self._heap and self._heap[0].time <= until:
            entry = heapq.heappop(self._heap)
            if entry.cancelled:
                continue
            self._now = entry.time
            entry.action()
            executed += 1
        self._now = until
        self._processed += executed
        return executed
