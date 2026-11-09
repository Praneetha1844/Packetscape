"""Result export: CSV files, a text table and optional matplotlib plots."""

from __future__ import annotations

import csv
from pathlib import Path

from packetscape.simulation import SimulationResult

FLOW_COLUMNS = (
    "flow_id",
    "kind",
    "sent_packets",
    "delivered_packets",
    "delivered_bytes",
    "dropped_queue",
    "dropped_loss",
    "throughput_mbps",
    "loss_ratio",
    "delay_mean_ms",
    "delay_p50_ms",
    "delay_p95_ms",
    "delay_p99_ms",
)


def _fmt(value: float | None, digits: int = 3) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def write_flows_csv(result: SimulationResult, path: Path) -> None:
    """One row per flow."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(FLOW_COLUMNS)
        for flow in result.flows:
            writer.writerow(
                [
                    flow.flow_id,
                    flow.kind,
                    flow.sent_packets,
                    flow.delivered_packets,
                    flow.delivered_bytes,
                    flow.dropped_queue,
                    flow.dropped_loss,
                    _fmt(flow.throughput_bps / 1e6, 6),
                    _fmt(flow.loss_ratio, 6),
                    _fmt(flow.delay_mean_ms),
                    _fmt(flow.delay_p50_ms),
                    _fmt(flow.delay_p95_ms),
                    _fmt(flow.delay_p99_ms),
                ]
            )


def write_cwnd_csv(result: SimulationResult, path: Path) -> None:
    """Congestion-window samples for every TCP flow (written when the window changes)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("flow_id", "time_s", "cwnd_packets"))
        for flow_id, trace in result.cwnd_traces.items():
            for time_s, cwnd in trace:
                writer.writerow((flow_id, f"{time_s:.6f}", f"{cwnd:.4f}"))


def format_table(result: SimulationResult) -> str:
    """Human-readable summary for the terminal."""
    header = (
        f"{'flow':<12}{'kind':<9}{'thr (Mb/s)':>12}{'loss':>9}"
        f"{'p50 (ms)':>11}{'p95 (ms)':>11}{'p99 (ms)':>11}"
    )
    lines = [
        f"scenario={result.name} seed={result.seed} duration={result.duration:g}s "
        f"events={result.events}",
        header,
        "-" * len(header),
    ]
    for flow in result.flows:
        lines.append(
            f"{flow.flow_id:<12}{flow.kind:<9}{flow.throughput_bps / 1e6:>12.3f}"
            f"{flow.loss_ratio:>9.4f}"
            f"{_fmt(flow.delay_p50_ms, 2) or '-':>11}"
            f"{_fmt(flow.delay_p95_ms, 2) or '-':>11}"
            f"{_fmt(flow.delay_p99_ms, 2) or '-':>11}"
        )
    lines.append(f"Jain fairness index (all flows): {result.jain_index:.4f}")
    return "\n".join(lines)
