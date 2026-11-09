from __future__ import annotations

import pytest

from packetscape.topology import LinkSpec, NoRouteError, Topology


def spec(a: str, b: str) -> LinkSpec:
    return LinkSpec(a, b, 1e6, 0.001)


def test_shortest_path_prefers_fewest_hops() -> None:
    links = [spec("a", "b"), spec("b", "c"), spec("c", "d"), spec("a", "d")]
    assert Topology(["a", "b", "c", "d"], links).shortest_path("a", "d") == ("a", "d")


def test_ties_break_alphabetically_and_deterministically() -> None:
    links = [spec("a", "c"), spec("a", "b"), spec("b", "d"), spec("c", "d")]
    assert Topology(["a", "b", "c", "d"], links).shortest_path("a", "d") == ("a", "b", "d")


def test_reverse_path_is_reverse_of_forward_path() -> None:
    topo = Topology(["a", "b", "c"], [spec("a", "b"), spec("b", "c")])
    assert topo.shortest_path("c", "a") == tuple(reversed(topo.shortest_path("a", "c")))


def test_disconnected_nodes_have_no_route() -> None:
    topo = Topology(["a", "b", "c"], [spec("a", "b")])
    with pytest.raises(NoRouteError):
        topo.shortest_path("a", "c")


def test_unknown_node_and_same_node_are_rejected() -> None:
    topo = Topology(["a", "b"], [spec("a", "b")])
    with pytest.raises(NoRouteError):
        topo.shortest_path("a", "zzz")
    with pytest.raises(NoRouteError):
        topo.shortest_path("a", "a")


def test_invalid_topologies_are_rejected() -> None:
    with pytest.raises(ValueError):
        Topology(["a", "a"], [])
    with pytest.raises(ValueError):
        Topology(["a", "b"], [spec("a", "x")])
    with pytest.raises(ValueError):
        Topology(["a", "b"], [spec("a", "b"), spec("b", "a")])


@pytest.mark.parametrize(
    "override",
    [{"bandwidth_bps": 0.0}, {"delay_s": -0.1}, {"loss_prob": 1.0}],
)
def test_link_spec_validates_parameters(override: dict[str, float]) -> None:
    params = {"bandwidth_bps": 1e6, "delay_s": 0.0, "loss_prob": 0.0}
    params.update(override)
    with pytest.raises(ValueError):
        LinkSpec(
            "a",
            "b",
            bandwidth_bps=params["bandwidth_bps"],
            delay_s=params["delay_s"],
            loss_prob=params["loss_prob"],
        )
