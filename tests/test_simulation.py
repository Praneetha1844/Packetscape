from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from packetscape.config import load_config, parse_config
from packetscape.simulation import Simulation, child_rng
from packetscape.topology import NoRouteError

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def two_node(flow: dict[str, Any], *, loss: float = 0.0, duration: float = 5.0) -> dict[str, Any]:
    return {
        "seed": 1,
        "duration": duration,
        "nodes": ["a", "b"],
        "links": [
            {
                "a": "a",
                "b": "b",
                "bandwidth_mbps": 10,
                "delay_ms": 5,
                "loss_prob": loss,
                "queue": {"type": "droptail", "capacity": 100},
            }
        ],
        "flows": [{"id": "f", "src": "a", "dst": "b", **flow}],
    }


def test_finite_tcp_transfer_over_a_clean_link_delivers_everything() -> None:
    result = Simulation(parse_config(two_node({"kind": "tcp", "packets": 20}))).run()
    (flow,) = result.flows
    assert flow.sent_packets == 20
    assert flow.delivered_packets == 20
    assert flow.dropped_queue == 0
    assert flow.dropped_loss == 0
    assert result.ack_drops == 0


def test_tcp_recovers_from_random_loss_and_delivers_every_packet() -> None:
    config = parse_config(
        two_node({"kind": "tcp", "packets": 200}, loss=0.02, duration=120.0)
    )
    (flow,) = Simulation(config).run().flows
    assert flow.delivered_packets == 200
    assert flow.sent_packets >= 200  # retransmissions may add to the count


def test_cbr_source_sends_at_the_configured_rate() -> None:
    config = parse_config(two_node({"kind": "cbr", "rate_mbps": 1, "packet_size": 1000}, duration=1))
    (flow,) = Simulation(config).run().flows
    assert 124 <= flow.sent_packets <= 126  # 125 packets per second
    assert flow.delivered_packets <= flow.sent_packets


def test_identical_seed_gives_identical_results() -> None:
    config = load_config(EXAMPLES / "tcp_vs_udp.yaml")
    first = Simulation(config).run()
    second = Simulation(config).run()
    assert first.flows == second.flows
    assert first.events == second.events
    assert first.cwnd_traces == second.cwnd_traces


def test_delivery_never_exceeds_transmission() -> None:
    result = Simulation(load_config(EXAMPLES / "red_vs_droptail.yaml")).run()
    for flow in result.flows:
        assert flow.delivered_packets <= flow.sent_packets
        assert 0.0 <= flow.loss_ratio <= 1.0
    assert 0.0 < result.jain_index <= 1.0


def test_simulation_cannot_be_run_twice() -> None:
    simulation = Simulation(parse_config(two_node({"kind": "tcp", "packets": 5})))
    simulation.run()
    with pytest.raises(RuntimeError):
        simulation.run()


def test_unreachable_flow_is_reported_when_building() -> None:
    data = two_node({"kind": "tcp"})
    data["nodes"] = ["a", "b", "island"]
    data["flows"][0]["dst"] = "island"
    with pytest.raises(NoRouteError):
        Simulation(parse_config(data))


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.yaml")), ids=lambda p: p.name)
def test_every_example_scenario_builds(path: Path) -> None:
    Simulation(load_config(path))


def test_child_rngs_are_independent_and_reproducible() -> None:
    assert child_rng(1, "x").random() == child_rng(1, "x").random()
    assert child_rng(1, "x").random() != child_rng(1, "y").random()
    assert child_rng(1, "x").random() != child_rng(2, "x").random()
