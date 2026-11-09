"""Scenario configuration: typed dataclasses and strict YAML validation.

Unknown keys are rejected so that typos fail loudly instead of being silently
ignored. All validation errors raise :class:`ConfigError` with the path of the
offending field.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

QUEUE_TYPES = ("droptail", "red")
FLOW_KINDS = ("tcp", "cbr", "poisson")
CC_NAMES = ("fixed", "aimd", "cubic")
_FLOW_KEYS = {
    "id",
    "src",
    "dst",
    "kind",
    "start",
    "stop",
    "packet_size",
    "cc",
    "window",
    "rate_mbps",
    "packets",
}


class ConfigError(ValueError):
    """Raised when a scenario file is malformed or inconsistent."""


_MISSING: Any = object()


def _mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{where}: expected a mapping")
    return value


def _check_keys(data: Mapping[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(f"{where}: unknown key(s) {', '.join(unknown)}")


def _number(
    data: Mapping[str, Any],
    key: str,
    where: str,
    default: Any = _MISSING,
    *,
    gt: float | None = None,
    ge: float | None = None,
    lt: float | None = None,
    le: float | None = None,
) -> float:
    if key not in data:
        if default is _MISSING:
            raise ConfigError(f"{where}: missing required key {key!r}")
        return float(default)
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(f"{where}.{key}: expected a number")
    number = float(value)
    if number != number:  # NaN
        raise ConfigError(f"{where}.{key}: NaN is not allowed")
    if gt is not None and not number > gt:
        raise ConfigError(f"{where}.{key}: must be > {gt}")
    if ge is not None and not number >= ge:
        raise ConfigError(f"{where}.{key}: must be >= {ge}")
    if lt is not None and not number < lt:
        raise ConfigError(f"{where}.{key}: must be < {lt}")
    if le is not None and not number <= le:
        raise ConfigError(f"{where}.{key}: must be <= {le}")
    return number


def _integer(
    data: Mapping[str, Any],
    key: str,
    where: str,
    default: Any = _MISSING,
    *,
    ge: int | None = None,
) -> int:
    if key not in data:
        if default is _MISSING:
            raise ConfigError(f"{where}: missing required key {key!r}")
        return int(default)
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{where}.{key}: expected an integer")
    if ge is not None and value < ge:
        raise ConfigError(f"{where}.{key}: must be >= {ge}")
    return value


def _string(data: Mapping[str, Any], key: str, where: str, default: Any = _MISSING) -> str:
    if key not in data:
        if default is _MISSING:
            raise ConfigError(f"{where}: missing required key {key!r}")
        return str(default)
    value = data[key]
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{where}.{key}: expected a non-empty string")
    return value


@dataclass(frozen=True)
class QueueConfig:
    type: str = "droptail"
    capacity: int = 100
    min_threshold: float | None = None
    max_threshold: float | None = None
    max_p: float = 0.1
    weight: float = 0.002


@dataclass(frozen=True)
class LinkConfig:
    a: str
    b: str
    bandwidth_mbps: float
    delay_ms: float
    loss_prob: float = 0.0
    queue: QueueConfig = field(default_factory=QueueConfig)


@dataclass(frozen=True)
class FlowConfig:
    id: str
    src: str
    dst: str
    kind: str
    start: float = 0.0
    stop: float | None = None
    packet_size: int = 1000
    cc: str = "aimd"
    window: float = 10.0
    rate_mbps: float | None = None
    packets: int | None = None


@dataclass(frozen=True)
class SimConfig:
    seed: int
    duration: float
    nodes: tuple[str, ...]
    links: tuple[LinkConfig, ...]
    flows: tuple[FlowConfig, ...]
    name: str = "scenario"


def _parse_queue(raw: object, where: str) -> QueueConfig:
    data = _mapping(raw, where)
    _check_keys(
        data, {"type", "capacity", "min_threshold", "max_threshold", "max_p", "weight"}, where
    )
    qtype = _string(data, "type", where, "droptail")
    if qtype not in QUEUE_TYPES:
        raise ConfigError(f"{where}.type: expected one of {', '.join(QUEUE_TYPES)}")
    capacity = _integer(data, "capacity", where, 100, ge=1)
    max_p = _number(data, "max_p", where, 0.1, gt=0, le=1)
    weight = _number(data, "weight", where, 0.002, gt=0, le=1)
    min_t: float | None = None
    max_t: float | None = None
    if qtype == "red":
        min_t = _number(data, "min_threshold", where, capacity * 0.25, gt=0)
        max_t = _number(data, "max_threshold", where, capacity * 0.75, gt=0)
        if not min_t < max_t <= capacity:
            raise ConfigError(f"{where}: thresholds must satisfy 0 < min < max <= capacity")
    elif "min_threshold" in data or "max_threshold" in data:
        raise ConfigError(f"{where}: thresholds are only valid for type 'red'")
    return QueueConfig(qtype, capacity, min_t, max_t, max_p, weight)


def _parse_link(raw: object, where: str, nodes: set[str]) -> LinkConfig:
    data = _mapping(raw, where)
    _check_keys(data, {"a", "b", "bandwidth_mbps", "delay_ms", "loss_prob", "queue"}, where)
    a = _string(data, "a", where)
    b = _string(data, "b", where)
    for endpoint in (a, b):
        if endpoint not in nodes:
            raise ConfigError(f"{where}: unknown node {endpoint!r}")
    if a == b:
        raise ConfigError(f"{where}: a link must connect two different nodes")
    queue = _parse_queue(data["queue"], f"{where}.queue") if "queue" in data else QueueConfig()
    return LinkConfig(
        a=a,
        b=b,
        bandwidth_mbps=_number(data, "bandwidth_mbps", where, gt=0),
        delay_ms=_number(data, "delay_ms", where, ge=0),
        loss_prob=_number(data, "loss_prob", where, 0.0, ge=0, lt=1),
        queue=queue,
    )


def _parse_flow(raw: object, where: str, nodes: set[str], duration: float) -> FlowConfig:
    data = _mapping(raw, where)
    _check_keys(data, _FLOW_KEYS, where)
    kind = _string(data, "kind", where)
    if kind not in FLOW_KINDS:
        raise ConfigError(f"{where}.kind: expected one of {', '.join(FLOW_KINDS)}")
    src = _string(data, "src", where)
    dst = _string(data, "dst", where)
    for endpoint in (src, dst):
        if endpoint not in nodes:
            raise ConfigError(f"{where}: unknown node {endpoint!r}")
    if src == dst:
        raise ConfigError(f"{where}: src and dst must differ")
    start = _number(data, "start", where, 0.0, ge=0, lt=duration)
    stop = _number(data, "stop", where, duration, gt=start, le=duration) if "stop" in data else None
    cc = _string(data, "cc", where, "aimd")
    if cc not in CC_NAMES:
        raise ConfigError(f"{where}.cc: expected one of {', '.join(CC_NAMES)}")
    rate: float | None = None
    if kind in ("cbr", "poisson"):
        rate = _number(data, "rate_mbps", where, gt=0)
    elif "rate_mbps" in data:
        raise ConfigError(f"{where}: rate_mbps is only valid for cbr and poisson flows")
    packets = _integer(data, "packets", where, ge=1) if "packets" in data else None
    if packets is not None and kind != "tcp":
        raise ConfigError(f"{where}: packets is only valid for tcp flows")
    if kind != "tcp" and ("cc" in data or "window" in data):
        raise ConfigError(f"{where}: cc and window are only valid for tcp flows")
    if "window" in data and cc != "fixed":
        raise ConfigError(f"{where}: window is only valid with cc: fixed")
    return FlowConfig(
        id=_string(data, "id", where),
        src=src,
        dst=dst,
        kind=kind,
        start=start,
        stop=stop,
        packet_size=_integer(data, "packet_size", where, 1000, ge=64),
        cc=cc,
        window=_number(data, "window", where, 10.0, ge=1),
        rate_mbps=rate,
        packets=packets,
    )


def parse_config(raw: object, name: str = "scenario") -> SimConfig:
    """Validate a parsed YAML document and return a :class:`SimConfig`."""
    data = _mapping(raw, "config")
    _check_keys(data, {"seed", "duration", "nodes", "links", "flows"}, "config")
    seed = _integer(data, "seed", "config", 0)
    duration = _number(data, "duration", "config", gt=0)

    raw_nodes = data.get("nodes")
    if not isinstance(raw_nodes, list) or len(raw_nodes) < 2:
        raise ConfigError("config.nodes: expected a list of at least two node names")
    if not all(isinstance(n, str) and n for n in raw_nodes):
        raise ConfigError("config.nodes: node names must be non-empty strings")
    if len(set(raw_nodes)) != len(raw_nodes):
        raise ConfigError("config.nodes: duplicate node names")
    nodes = set(raw_nodes)

    raw_links = data.get("links")
    if not isinstance(raw_links, list) or not raw_links:
        raise ConfigError("config.links: expected a non-empty list")
    links = tuple(
        _parse_link(item, f"config.links[{i}]", nodes) for i, item in enumerate(raw_links)
    )
    seen_pairs: set[frozenset[str]] = set()
    for i, link in enumerate(links):
        pair = frozenset((link.a, link.b))
        if pair in seen_pairs:
            raise ConfigError(
                f"config.links[{i}]: duplicate link between {link.a!r} and {link.b!r}"
            )
        seen_pairs.add(pair)

    raw_flows = data.get("flows")
    if not isinstance(raw_flows, list) or not raw_flows:
        raise ConfigError("config.flows: expected a non-empty list")
    flows = tuple(
        _parse_flow(item, f"config.flows[{i}]", nodes, duration) for i, item in enumerate(raw_flows)
    )
    ids = [flow.id for flow in flows]
    if len(set(ids)) != len(ids):
        raise ConfigError("config.flows: duplicate flow ids")

    return SimConfig(
        seed=seed,
        duration=duration,
        nodes=tuple(raw_nodes),
        links=links,
        flows=flows,
        name=name,
    )


def load_config(path: str | Path) -> SimConfig:
    """Read and validate a YAML scenario file."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read {file_path}: {exc.strerror or exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{file_path}: invalid YAML: {exc}") from exc
    return parse_config(raw, name=file_path.stem)
