"""Queue disciplines: drop-tail FIFO and Random Early Detection (RED).

Capacities and thresholds are expressed in packets, not bytes (see
``docs/model-and-limits.md``).
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections import deque

from packetscape.packet import Packet


class QueueDiscipline(ABC):
    """Interface implemented by every queue discipline."""

    @abstractmethod
    def enqueue(self, packet: Packet, now: float) -> bool:
        """Try to enqueue. Returns ``False`` if the packet was dropped."""

    @abstractmethod
    def dequeue(self, now: float) -> Packet | None:
        """Remove and return the head-of-line packet, or ``None`` if empty."""

    @abstractmethod
    def __len__(self) -> int: ...


class DropTailQueue(QueueDiscipline):
    """FIFO queue that drops arrivals when full."""

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._queue: deque[Packet] = deque()

    def enqueue(self, packet: Packet, now: float) -> bool:
        if len(self._queue) >= self._capacity:
            return False
        self._queue.append(packet)
        return True

    def dequeue(self, now: float) -> Packet | None:
        return self._queue.popleft() if self._queue else None

    def __len__(self) -> int:
        return len(self._queue)


class RedQueue(QueueDiscipline):
    """Random Early Detection (Floyd and Jacobson, 1993), simplified.

    The average queue length is an exponentially weighted moving average updated
    on each arrival. Between ``min_threshold`` and ``max_threshold`` arrivals are
    dropped with a probability that grows linearly up to ``max_p``, spaced out
    using the packets-since-last-drop count. The idle-time correction of the
    original algorithm is intentionally omitted.
    """

    def __init__(
        self,
        capacity: int,
        min_threshold: float,
        max_threshold: float,
        max_p: float,
        weight: float,
        rng: random.Random,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        if not 0 < min_threshold < max_threshold <= capacity:
            raise ValueError("thresholds must satisfy 0 < min < max <= capacity")
        if not 0 < max_p <= 1:
            raise ValueError("max_p must be in (0, 1]")
        if not 0 < weight <= 1:
            raise ValueError("weight must be in (0, 1]")
        self._capacity = capacity
        self._min = min_threshold
        self._max = max_threshold
        self._max_p = max_p
        self._weight = weight
        self._rng = rng
        self._queue: deque[Packet] = deque()
        self._avg = 0.0
        self._count = -1  # packets since last drop while between thresholds; -1 = below min

    @property
    def average_length(self) -> float:
        return self._avg

    def enqueue(self, packet: Packet, now: float) -> bool:
        self._avg = (1.0 - self._weight) * self._avg + self._weight * len(self._queue)
        if len(self._queue) >= self._capacity:
            self._count = 0
            return False
        if self._avg < self._min:
            self._count = -1
            self._queue.append(packet)
            return True
        if self._avg >= self._max:
            self._count = 0
            return False
        self._count += 1
        base = self._max_p * (self._avg - self._min) / (self._max - self._min)
        denominator = 1.0 - self._count * base
        probability = 1.0 if denominator <= 0.0 else min(1.0, base / denominator)
        if self._rng.random() < probability:
            self._count = 0
            return False
        self._queue.append(packet)
        return True

    def dequeue(self, now: float) -> Packet | None:
        return self._queue.popleft() if self._queue else None

    def __len__(self) -> int:
        return len(self._queue)
