"""Local maps for the Coupled Map Lattice.

A local map f: [0, 1] -> [0, 1] is applied element-wise to the lattice before
coupling. Any map satisfying that bound keeps the coupled state in [0, 1],
because the coupling step is a convex combination of f-values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


class LocalMap(Protocol):
    def __call__(self, x: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True)
class LogisticMap:
    """f(x) = r * x * (1 - x), with r in [0, 4] so that f([0,1]) is within [0,1]."""

    r: float = 3.9

    def __post_init__(self) -> None:
        if not 0.0 <= self.r <= 4.0:
            raise ValueError(f"r must be in [0, 4], got {self.r}")

    def __call__(self, x: np.ndarray) -> np.ndarray:
        return self.r * x * (1.0 - x)
