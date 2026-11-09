"""Congestion-control algorithms operating on a packet-granular window.

All three implementations are deliberate simplifications intended for
comparison studies, not faithful reproductions of any operating-system stack
(see ``docs/model-and-limits.md``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

INITIAL_SSTHRESH = 1e9
MIN_WINDOW = 2.0


class CongestionControl(ABC):
    """Window state machine driven by the TCP-like sender."""

    name: str

    def __init__(self, initial_cwnd: float) -> None:
        if initial_cwnd < 1:
            raise ValueError("initial_cwnd must be >= 1")
        self.cwnd = float(initial_cwnd)
        self.ssthresh = INITIAL_SSTHRESH

    @abstractmethod
    def on_ack(self, newly_acked: int, rtt: float | None, now: float) -> None:
        """Called when a cumulative ACK advances the window by ``newly_acked`` packets."""

    @abstractmethod
    def on_fast_retransmit(self, now: float) -> None:
        """Called on the third duplicate ACK."""

    @abstractmethod
    def on_timeout(self, now: float) -> None:
        """Called when the retransmission timer expires."""


class FixedWindow(CongestionControl):
    """Constant window; useful as a baseline that never reacts to congestion."""

    name = "fixed"

    def __init__(self, window: float) -> None:
        super().__init__(window)

    def on_ack(self, newly_acked: int, rtt: float | None, now: float) -> None:
        return

    def on_fast_retransmit(self, now: float) -> None:
        return

    def on_timeout(self, now: float) -> None:
        return


class Aimd(CongestionControl):
    """Reno-like additive-increase, multiplicative-decrease.

    Slow start doubles the window each RTT until ``ssthresh``; congestion
    avoidance then adds one packet per RTT. Fast retransmit halves the window;
    a timeout resets it to one packet.
    """

    name = "aimd"

    def __init__(self, initial_cwnd: float = 2.0) -> None:
        super().__init__(initial_cwnd)

    def on_ack(self, newly_acked: int, rtt: float | None, now: float) -> None:
        for _ in range(newly_acked):
            if self.cwnd < self.ssthresh:
                self.cwnd += 1.0
            else:
                self.cwnd += 1.0 / self.cwnd

    def on_fast_retransmit(self, now: float) -> None:
        self.ssthresh = max(self.cwnd / 2.0, MIN_WINDOW)
        self.cwnd = self.ssthresh

    def on_timeout(self, now: float) -> None:
        self.ssthresh = max(self.cwnd / 2.0, MIN_WINDOW)
        self.cwnd = 1.0


class CubicLite(CongestionControl):
    """A simplified CUBIC-style controller.

    After a loss the window follows ``C * (t - K)^3 + w_max`` where ``t`` is the
    time since the loss and ``K`` is the time needed to climb back to the
    pre-loss window. The TCP-friendly region, hybrid slow start and
    fast-convergence logic of the real algorithm are not implemented.
    """

    name = "cubic"

    C = 0.4
    BETA = 0.7

    def __init__(self, initial_cwnd: float = 2.0) -> None:
        super().__init__(initial_cwnd)
        self._w_max = 0.0
        self._epoch_start: float | None = None
        self._k = 0.0

    def on_ack(self, newly_acked: int, rtt: float | None, now: float) -> None:
        for _ in range(newly_acked):
            if self.cwnd < self.ssthresh:
                self.cwnd += 1.0
                continue
            if self._epoch_start is None:
                self._epoch_start = now
                if self._w_max < self.cwnd:
                    self._w_max = self.cwnd
                    self._k = 0.0
                else:
                    self._k = ((self._w_max - self.cwnd) / self.C) ** (1.0 / 3.0)
            t = now - self._epoch_start
            target = self.C * (t - self._k) ** 3 + self._w_max
            if target > self.cwnd:
                self.cwnd += (target - self.cwnd) / self.cwnd
            else:
                self.cwnd += 0.01 / self.cwnd  # minimal probing while below the curve

    def on_fast_retransmit(self, now: float) -> None:
        self._epoch_start = None
        self._w_max = self.cwnd
        self.cwnd = max(self.cwnd * self.BETA, MIN_WINDOW)
        self.ssthresh = self.cwnd

    def on_timeout(self, now: float) -> None:
        self._epoch_start = None
        self._w_max = self.cwnd
        self.ssthresh = max(self.cwnd * self.BETA, MIN_WINDOW)
        self.cwnd = 1.0


def make_congestion_control(name: str, window: float) -> CongestionControl:
    """Create a controller by name. ``window`` is used only by ``fixed``."""
    if name == "fixed":
        return FixedWindow(window)
    if name == "aimd":
        return Aimd()
    if name == "cubic":
        return CubicLite()
    raise ValueError(f"unknown congestion control {name!r}; expected fixed, aimd or cubic")
