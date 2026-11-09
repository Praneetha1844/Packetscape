"""Optional matplotlib plots (install with ``pip install packetscape[plots]``)."""

from __future__ import annotations

from pathlib import Path

from packetscape.simulation import SimulationResult


def plot_results(result: SimulationResult, out_dir: Path) -> list[Path]:
    """Write throughput, latency and congestion-window figures; return their paths."""
    try:
        import matplotlib

        matplotlib.use("Agg")  # headless: no display required
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise RuntimeError(
            "plotting requires matplotlib: pip install 'packetscape[plots]'"
        ) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    ids = [flow.flow_id for flow in result.flows]

    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.bar(ids, [flow.throughput_bps / 1e6 for flow in result.flows])
    ax.set_ylabel("Throughput (Mb/s)")
    ax.set_title(f"Throughput per flow (Jain index {result.jain_index:.3f})")
    path = out_dir / "throughput.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    written.append(path)

    measured = [flow for flow in result.flows if flow.delay_p50_ms is not None]
    if measured:
        fig, ax = plt.subplots(figsize=(6, 3.5))
        width = 0.25
        series = {
            "p50": [flow.delay_p50_ms or 0.0 for flow in measured],
            "p95": [flow.delay_p95_ms or 0.0 for flow in measured],
            "p99": [flow.delay_p99_ms or 0.0 for flow in measured],
        }
        for offset, (label, values) in enumerate(series.items()):
            positions = [i + (offset - 1) * width for i in range(len(measured))]
            ax.bar(positions, values, width, label=label)
        ax.set_xticks(range(len(measured)))
        ax.set_xticklabels([flow.flow_id for flow in measured])
        ax.set_ylabel("One-way delay (ms)")
        ax.legend()
        path = out_dir / "latency.png"
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        written.append(path)

    if result.cwnd_traces:
        fig, ax = plt.subplots(figsize=(6, 3.5))
        for flow_id, trace in result.cwnd_traces.items():
            if trace:
                ax.step([t for t, _ in trace], [w for _, w in trace], where="post", label=flow_id)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("cwnd (packets)")
        ax.legend()
        path = out_dir / "cwnd.png"
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        written.append(path)
    return written
