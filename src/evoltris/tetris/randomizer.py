"""7-bag piece randomizer: each consecutive group of 7 contains every piece once."""

from __future__ import annotations

import random
from collections import deque

from evoltris.tetris.pieces import PieceType


class BagRandomizer:
    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._queue: deque[PieceType] = deque()

    def _refill(self) -> None:
        bag = list(PieceType)
        self._rng.shuffle(bag)
        self._queue.extend(bag)

    def next(self) -> PieceType:
        if not self._queue:
            self._refill()
        return self._queue.popleft()

    def peek(self, n: int) -> list[PieceType]:
        while len(self._queue) < n:
            self._refill()
        return list(self._queue)[:n]
