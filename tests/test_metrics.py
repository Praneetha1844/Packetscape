from __future__ import annotations

import pytest

from packetscape.metrics import MetricsCollector, jain_index, percentile
from packetscape.packet import Packet


def test_percentile_uses_nearest_rank() -> None:
    values = [float(v) for v in range(1, 11)]
    assert percentile(values, 50) == 5
    assert percentile(values, 90) == 9
    assert percentile(values, 100) == 10
    assert percentile([3.0], 99) == 3.0


@pytest.mark.parametrize(("values", "pct"), [([], 50), ([1.0], 0), ([1.0], 101)])
def test_percentile_rejects_bad_input(values: list[float], pct: float) -> None:
    with pytest.raises(ValueError):
        percentile(values, pct)


def test_jain_index_bounds() -> None:
    assert jain_index([5.0, 5.0, 5.0]) == pytest.approx(1.0)
    assert jain_index([4.0, 0.0, 0.0, 0.0]) == pytest.approx(0.25)
    assert jain_index([0.0, 0.0]) == 1.0
    assert 0.5 < jain_index([1.0, 3.0]) < 1.0


def test_jain_index_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        jain_index([])
    with pytest.raises(ValueError):
        jain_index([-1.0, 2.0])


def make_packet(seq: int, *, ack: bool = False) -> Packet:
    return Packet("f", seq, 1000, 1.0, ("a", "b"), is_ack=ack)


def test_summary_throughput_loss_and_delay() -> None:
    metrics = MetricsCollector()
    metrics.register_flow("f", "tcp", start=0.0)
    for seq in range(4):
        metrics.record_sent(make_packet(seq))
    metrics.record_delivery(make_packet(0), now=1.010)
    metrics.record_delivery(make_packet(1), now=1.020)
    metrics.record_drop(make_packet(2), "queue")
    metrics.record_drop(make_packet(3), "loss")

    (summary,) = metrics.summarize(duration=10.0)
    assert summary.throughput_bps == pytest.approx(2 * 1000 * 8 / 10.0)
    assert summary.loss_ratio == pytest.approx(0.5)
    assert summary.delay_p50_ms == pytest.approx(10.0)
    assert summary.delay_p99_ms == pytest.approx(20.0)
    assert summary.delay_mean_ms == pytest.approx(15.0)


def test_summary_without_deliveries_has_no_delay_statistics() -> None:
    metrics = MetricsCollector()
    metrics.register_flow("f", "cbr", start=0.0)
    (summary,) = metrics.summarize(duration=5.0)
    assert summary.throughput_bps == 0.0
    assert summary.delay_p50_ms is None


def test_ack_drops_are_counted_separately() -> None:
    metrics = MetricsCollector()
    metrics.register_flow("f", "tcp", start=0.0)
    metrics.record_drop(make_packet(0, ack=True), "queue")
    assert metrics.ack_drops == 1
    assert metrics.stats("f").dropped_queue == 0


def test_duplicate_flow_registration_is_rejected() -> None:
    metrics = MetricsCollector()
    metrics.register_flow("f", "tcp", start=0.0)
    with pytest.raises(ValueError):
        metrics.register_flow("f", "tcp", start=0.0)


def test_cwnd_trace_records_only_changes() -> None:
    metrics = MetricsCollector()
    metrics.register_flow("f", "tcp", start=0.0)
    metrics.record_cwnd("f", 0.0, 2.0)
    metrics.record_cwnd("f", 1.0, 2.0)
    metrics.record_cwnd("f", 2.0, 3.0)
    assert metrics.stats("f").cwnd_trace == [(0.0, 2.0), (2.0, 3.0)]
