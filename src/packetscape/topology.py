"""Static topology and hop-count shortest-path routing."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


class NoRouteError(ValueError):
    """Raised when no path exists between two nodes."""


@dataclass(frozen=True)
class LinkSpec:
    """Physical parameters of a bidirectional link (each direction is simulated separately)."""

    a: str
    b: str
    bandwidth_bps: float
    delay_s: float
    loss_prob: float = 0.0

    def __post_init__(self) -> None:
        if self.a == self.b:
            raise ValueError("a link must connect two different nodes")
        if self.bandwidth_bps <= 0:
            raise ValueError("bandwidth must be positive")
        if self.delay_s < 0:
            raise ValueError("delay must be >= 0")
        if not 0.0 <= self.loss_prob < 1.0:
            raise ValueError("loss_prob must be in [0, 1)")


class Topology:
    """An undirected graph of named nodes with deterministic shortest-path routing."""

    def __init__(self, nodes: list[str], links: list[LinkSpec]) -> None:
        if len(set(nodes)) != len(nodes):
            raise ValueError("duplicate node names")
        self._nodes = list(nodes)
        self._adjacency: dict[str, list[str]] = {n: [] for n in nodes}
        seen: set[frozenset[str]] = set()
        for link in links:
            for endpoint in (link.a, link.b):
                if endpoint not in self._adjacency:
                    raise ValueError(f"link references unknown node {endpoint!r}")
            key = frozenset((link.a, link.b))
            if key in seen:
                raise ValueError(f"duplicate link between {link.a!r} and {link.b!r}")
            seen.add(key)
            self._adjacency[link.a].append(link.b)
            self._adjacency[link.b].append(link.a)
        for neighbours in self._adjacency.values():
            neighbours.sort()  # deterministic tie-breaking

    @property
    def nodes(self) -> list[str]:
        return list(self._nodes)

    def shortest_path(self, src: str, dst: str) -> tuple[str, ...]:
        """Breadth-first path with the fewest hops; ties resolved alphabetically."""
        for name in (src, dst):
            if name not in self._adjacency:
                raise NoRouteError(f"unknown node {name!r}")
        if src == dst:
            raise NoRouteError("source and destination are the same node")
        parent: dict[str, str | None] = {src: None}
        frontier: deque[str] = deque([src])
        while frontier:
            current = frontier.popleft()
            if current == dst:
                break
            for neighbour in self._adjacency[current]:
                if neighbour not in parent:
                    parent[neighbour] = current
                    frontier.append(neighbour)
        if dst not in parent:
            raise NoRouteError(f"no route from {src!r} to {dst!r}")
        path: list[str] = []
        node: str | None = dst
        while node is not None:
            path.append(node)
            node = parent[node]
        return tuple(reversed(path))
