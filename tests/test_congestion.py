from __future__ import annotations

import pytest

from packetscape.congestion import Aimd, CubicLite, FixedWindow, make_congestion_control


def test_aimd_doubles_window_per_rtt_in_slow_start() -> None:
    cc = Aimd()
    assert cc.cwnd == 2.0
    cc.on_ack(2, rtt=0.05, now=0.1)
    assert cc.cwnd == 4.0


def test_aimd_adds_roughly_one_packet_per_rtt_in_congestion_avoidance() -> None:
    cc = Aimd()
    cc.cwnd = 10.0
    cc.ssthresh = 5.0
    cc.on_ack(10, rtt=0.05, now=1.0)
    assert 10.5 < cc.cwnd < 11.0


def test_aimd_halves_on_fast_retransmit_and_resets_on_timeout() -> None:
    cc = Aimd()
    cc.cwnd = 20.0
    cc.on_fast_retransmit(now=1.0)
    assert cc.cwnd == 10.0
    assert cc.ssthresh == 10.0
    cc.on_timeout(now=2.0)
    assert cc.cwnd == 1.0
    assert cc.ssthresh == 5.0


def test_aimd_window_never_drops_below_minimum_after_fast_retransmit() -> None:
    cc = Aimd()
    cc.cwnd = 2.0
    cc.on_fast_retransmit(now=0.0)
    assert cc.cwnd == 2.0


def test_fixed_window_ignores_all_signals() -> None:
    cc = FixedWindow(8)
    cc.on_ack(5, rtt=0.1, now=1.0)
    cc.on_fast_retransmit(now=2.0)
    cc.on_timeout(now=3.0)
    assert cc.cwnd == 8.0


def test_cubic_reduces_by_beta_on_loss_and_then_regrows() -> None:
    cc = CubicLite()
    cc.cwnd = 100.0
    cc.on_fast_retransmit(now=1.0)
    assert cc.cwnd == pytest.approx(70.0)
    assert cc.ssthresh == pytest.approx(70.0)
    # Early in the epoch the target curve is at or below the window; growth is minimal.
    cc.on_ack(1, rtt=0.05, now=1.0)
    assert cc.cwnd >= 70.0
    # Well past the inflection point the cubic curve pulls the window upwards.
    before = cc.cwnd
    for _ in range(50):
        cc.on_ack(1, rtt=0.05, now=12.0)
    assert cc.cwnd > before


def test_cubic_timeout_collapses_window_to_one() -> None:
    cc = CubicLite()
    cc.cwnd = 50.0
    cc.on_timeout(now=1.0)
    assert cc.cwnd == 1.0
    assert cc.ssthresh == pytest.approx(35.0)


def test_factory_creates_controllers_and_rejects_unknown_names() -> None:
    assert isinstance(make_congestion_control("aimd", 10), Aimd)
    assert isinstance(make_congestion_control("cubic", 10), CubicLite)
    fixed = make_congestion_control("fixed", 12)
    assert isinstance(fixed, FixedWindow)
    assert fixed.cwnd == 12.0
    with pytest.raises(ValueError, match="unknown congestion control"):
        make_congestion_control("bbr", 10)


def test_initial_window_must_be_at_least_one() -> None:
    with pytest.raises(ValueError):
        Aimd(initial_cwnd=0.5)
