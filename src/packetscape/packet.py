"""Packet representation shared by every layer of the simulator."""

from __future__ import annotations

from dataclasses import dataclass

ACK_SIZE_BYTES = 40


@dataclass(slots=True)
class Packet:
    """A packet travelling along a fixed, precomputed path.

    ``hop`` is the index into ``path`` of the node that currently holds the packet.
    ``seq`` is a packet-granular sequence number (not a byte offset). For ACKs,
    ``ack_no`` is the next sequence number the receiver expects (cumulative ACK).
    """

    flow_id: str
    seq: int
    size_bytes: int
    created_at: float
    path: tuple[str, ...]
    hop: int = 0
    is_ack: bool = False
    ack_no: int = 0

    def __post_init__(self) -> None:
        if self.size_bytes <= 0:
            raise ValueError("size_bytes must be positive")
        if len(self.path) < 2:
            raise ValueError("path must contain at least a source and a destination")
