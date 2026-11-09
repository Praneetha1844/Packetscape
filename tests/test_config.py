from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from packetscape.config import ConfigError, load_config, parse_config

VALID: dict[str, Any] = {
    "seed": 3,
    "duration": 10,
    "nodes": ["a", "b", "c"],
    "links": [
        {"a": "a", "b": "b", "bandwidth_mbps": 10, "delay_ms": 5},
        {
            "a": "b",
            "b": "c",
            "bandwidth_mbps": 5,
            "delay_ms": 10,
            "loss_prob": 0.01,
            "queue": {"type": "red", "capacity": 40, "min_threshold": 5, "max_threshold": 20},
        },
    ],
    "flows": [
        {"id": "t", "src": "a", "dst": "c", "kind": "tcp", "cc": "cubic"},
        {"id": "u", "src": "a", "dst": "c", "kind": "poisson", "rate_mbps": 1.5, "start": 1},
    ],
}


def mutated(**changes: Any) -> dict[str, Any]:
    data = copy.deepcopy(VALID)
    data.update(changes)
    return data


def test_valid_config_is_parsed() -> None:
    config = parse_config(VALID, name="demo")
    assert config.name == "demo"
    assert config.seed == 3
    assert config.duration == 10.0
    assert config.links[1].queue.type == "red"
    assert config.links[1].queue.max_threshold == 20
    assert config.flows[0].cc == "cubic"
    assert config.flows[1].rate_mbps == 1.5


def test_red_thresholds_default_to_fractions_of_capacity() -> None:
    data = mutated()
    data["links"][1]["queue"] = {"type": "red", "capacity": 40}
    queue = parse_config(data).links[1].queue
    assert (queue.min_threshold, queue.max_threshold) == (10.0, 30.0)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({**VALID, "surprise": 1}, "unknown key"),
        ({k: v for k, v in VALID.items() if k != "duration"}, "duration"),
        (mutated(duration=0), "duration"),
        (mutated(duration=True), "number"),
        (mutated(nodes=["a"]), "nodes"),
        (mutated(nodes=["a", "a"]), "duplicate"),
        (mutated(links=[]), "links"),
        (mutated(flows=[]), "flows"),
        ("not a mapping", "mapping"),
    ],
)
def test_top_level_validation(data: Any, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        parse_config(data)


def test_link_validation() -> None:
    bad_node = mutated()
    bad_node["links"][0]["b"] = "zzz"
    with pytest.raises(ConfigError, match="unknown node"):
        parse_config(bad_node)

    bad_loss = mutated()
    bad_loss["links"][0]["loss_prob"] = 1.0
    with pytest.raises(ConfigError, match="loss_prob"):
        parse_config(bad_loss)

    typo = mutated()
    typo["links"][0]["bandwith_mbps"] = 1
    with pytest.raises(ConfigError, match="unknown key"):
        parse_config(typo)


def test_queue_validation() -> None:
    bad_type = mutated()
    bad_type["links"][0]["queue"] = {"type": "wfq"}
    with pytest.raises(ConfigError, match="type"):
        parse_config(bad_type)

    bad_thresholds = mutated()
    bad_thresholds["links"][1]["queue"] = {
        "type": "red",
        "capacity": 10,
        "min_threshold": 8,
        "max_threshold": 4,
    }
    with pytest.raises(ConfigError, match="thresholds"):
        parse_config(bad_thresholds)

    stray = mutated()
    stray["links"][0]["queue"] = {"type": "droptail", "min_threshold": 1}
    with pytest.raises(ConfigError, match="only valid for type 'red'"):
        parse_config(stray)


def test_flow_validation() -> None:
    duplicate = mutated()
    duplicate["flows"][1]["id"] = "t"
    with pytest.raises(ConfigError, match="duplicate flow ids"):
        parse_config(duplicate)

    missing_rate = mutated()
    del missing_rate["flows"][1]["rate_mbps"]
    with pytest.raises(ConfigError, match="rate_mbps"):
        parse_config(missing_rate)

    tcp_with_rate = mutated()
    tcp_with_rate["flows"][0]["rate_mbps"] = 1
    with pytest.raises(ConfigError, match="only valid for cbr"):
        parse_config(tcp_with_rate)

    same_endpoints = mutated()
    same_endpoints["flows"][0]["dst"] = "a"
    with pytest.raises(ConfigError, match="differ"):
        parse_config(same_endpoints)

    late_start = mutated()
    late_start["flows"][0]["start"] = 10
    with pytest.raises(ConfigError, match="start"):
        parse_config(late_start)

    bad_cc = mutated()
    bad_cc["flows"][0]["cc"] = "bbr"
    with pytest.raises(ConfigError, match="cc"):
        parse_config(bad_cc)


def test_load_config_reads_yaml(tmp_path: Path) -> None:
    path = tmp_path / "demo.yaml"
    path.write_text(
        "duration: 5\nnodes: [a, b]\n"
        "links:\n  - {a: a, b: b, bandwidth_mbps: 10, delay_ms: 1}\n"
        "flows:\n  - {id: f, src: a, dst: b, kind: tcp}\n",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.name == "demo"
    assert config.seed == 0


def test_load_config_reports_missing_file_and_bad_yaml(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="cannot read"):
        load_config(tmp_path / "absent.yaml")
    broken = tmp_path / "broken.yaml"
    broken.write_text("nodes: [a, b\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(broken)
