"""Conway's Game of Life engine (B3/S23).

Rules (unchanged from Conway):
1. A live cell with < 2 live neighbours dies (underpopulation).
2. A live cell with 2 or 3 live neighbours survives.
3. A live cell with > 3 live neighbours dies (overpopulation).
4. A dead cell with exactly 3 live neighbours becomes alive (reproduction).

States are strictly binary (``np.uint8`` 0/1).
"""

from __future__ import annotations

import numpy as np

from evoltris.config import BoundaryMode, LifeConfig
from evoltris.core.grid import moore_neighbour_sum


def life_step(grid: np.ndarray, boundary: BoundaryMode = "fixed") -> np.ndarray:
    """Return the next generation of ``grid``. Pure function; input is not modified."""
    alive = grid.astype(bool)
    n = moore_neighbour_sum(alive.astype(np.uint8), boundary, fill=0)
    born = ~alive & (n == 3)
    survives = alive & ((n == 2) | (n == 3))
    return (born | survives).astype(np.uint8)


class LifeEngine:
    """Holds a Game of Life grid and advances it one generation at a time."""

    def __init__(self, shape: tuple[int, int], config: LifeConfig | None = None) -> None:
        self.config = config or LifeConfig()
        self.grid = np.zeros(shape, dtype=np.uint8)
        self.generation = 0

    def randomize(self, density: float | None = None, seed: int | None = None) -> None:
        d = self.config.initial_density if density is None else density
        rng = np.random.default_rng(self.config.seed if seed is None else seed)
        self.grid = (rng.random(self.grid.shape) < d).astype(np.uint8)
        self.generation = 0

    def set_grid(self, grid: np.ndarray) -> None:
        if grid.shape != self.grid.shape:
            raise ValueError(f"shape mismatch: {grid.shape} != {self.grid.shape}")
        self.grid = (np.asarray(grid) != 0).astype(np.uint8)

    def step(self) -> None:
        self.grid = life_step(self.grid, self.config.boundary)
        self.generation += 1

    @property
    def population(self) -> int:
        return int(self.grid.sum())
