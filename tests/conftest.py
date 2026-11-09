"""Shared test helpers."""

from __future__ import annotations

import random


class FixedRandom(random.Random):
    """A RNG whose ``random()`` always returns the same value."""

    def __init__(self, value: float) -> None:
        super().__init__(0)
        self._value = value

    def random(self) -> float:
        return self._value
