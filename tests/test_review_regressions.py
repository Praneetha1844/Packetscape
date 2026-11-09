"""Regression tests for problems found in review: config checks, CLI errors, receiver ACKs."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from packetscape.cli import main
from packetscape.config import ConfigError, parse_config
from packetscape.events import Scheduler
from packetscape.metrics import MetricsCollector
from packetscape.packet import Packet
from packetscape.transport import TcpReceiver

BASE: dict[str, Any] = {
    "seed": 1,
    "duration": 5,
    "nodes": ["a", "b", "c"],
    "links": [
        {"a": "a", "b": "b", "bandwidth_mbps": 10, "delay_ms": 1},
        {"a": "b", "b": "c", "bandwidth_mbps": 10, "delay_ms": 1},
    ],
    "flows": [{"id": "t", "src": "a", "dst": "c", "kind": "tcp"}],
}


def variant(**flow_changes: Any) -> dict[str, Any]:
    data = copy.deepcopy(BASE)
    data["flows"][0].update(flow_changes)
    return data


# ---- scenario validation ---------------------------------------------------------------


def test_duplicate_links_are_a_config_error_in_either_direction() -> None:
    data = copy.deepcopy(BASE)
    data["links"].append({"a": "b", "b": "a", "bandwidth_mbps": 1, "delay_ms": 1})
    with pytest.raises(ConfigError, match=r"links\[2\].*duplicate link"):
        parse_config(data)


def test_cc_and_window_are_rejected_on_open_loop_flows() -> None:
    for extra in ({"cc": "aimd"}, {"window": 5}):
        data = variant(kind="cbr", rate_mbps=1, **extra)
        with pytest.raises(ConfigError, match="only valid for tcp"):
            parse_config(data)


def test_window_requires_the_fixed_controller() -> None:
    with pytest.raises(ConfigError, match="cc: fixed"):
        parse_config(variant(cc="aimd", window=5))
    config = parse_config(variant(cc="fixed", window=5))
    assert config.flows[0].window == 5.0


# ---- CLI -------------------------------------------------------------------------------


def test_unwritable_output_directory_is_reported_not_raised(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scenario = tmp_path / "s.yaml"
    scenario.write_text(
        "seed: 1\nduration: 2\nnodes: [a, b]\nlinks:\n"
        "  - {a: a, b: b, bandwidth_mbps: 10, delay_ms: 1}\n"
        "flows:\n  - {id: f, src: a, dst: b, kind: tcp, packets: 5}\n",
        encoding="utf-8",
    )
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("occupied", encoding="utf-8")
    assert main(["run", str(scenario), "--out", str(blocker)]) == 2
    assert "cannot write results" in capsys.readouterr().err


# ---- receiver --------------------------------------------------------------------------


class RecordingNetwork:
    """Stands in for Network: keeps every packet handed to `inject`."""

    def __init__(self) -> None:
        self.sent: list[Packet] = []

    def inject(self, packet: Packet) -> None:
        self.sent.append(packet)


def make_receiver() -> tuple[TcpReceiver, RecordingNetwork, MetricsCollector]:
    metrics = MetricsCollector()
    metrics.register_flow("f", "tcp", 0.0)
    network = RecordingNetwork()
    receiver = TcpReceiver(
        flow_id="f",
        reverse_path=("b", "a"),
        scheduler=Scheduler(),
        network=network,  # type: ignore[arg-type]
        metrics=metrics,
    )
    return receiver, network, metrics


def data(seq: int) -> Packet:
    return Packet("f", seq, 1000, 0.0, ("a", "b"))


def test_receiver_acks_cumulatively_and_fills_holes() -> None:
    receiver, network, _ = make_receiver()
    for seq in (0, 2, 1):
        receiver.on_data(data(seq))
    assert [p.ack_no for p in network.sent] == [1, 1, 3]
    assert all(p.is_ack for p in network.sent)


def test_duplicate_data_is_acked_but_not_counted_twice() -> None:
    receiver, network, metrics = make_receiver()
    for seq in (0, 1, 1, 0):
        receiver.on_data(data(seq))
    assert [p.ack_no for p in network.sent] == [1, 2, 2, 2]
    assert metrics.stats("f").delivered_packets == 2
