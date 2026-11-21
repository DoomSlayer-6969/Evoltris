"""Grid neighbourhood helpers shared by the cellular engines.

Both functions return, for every cell, the *sum* of its neighbours' values
under the requested boundary mode. They are vectorised with numpy padding so
a step over the whole board is a handful of array operations.
"""

from __future__ import annotations

import numpy as np

from evoltris.config import BoundaryMode

_PAD_MODE = {"fixed": "constant", "periodic": "wrap", "reflective": "edge"}


def _pad(grid: np.ndarray, boundary: BoundaryMode, fill: float) -> np.ndarray:
    try:
        mode = _PAD_MODE[boundary]
    except KeyError:
        raise ValueError(f"unknown boundary mode: {boundary!r}") from None
    if mode == "constant":
        return np.pad(grid, 1, mode="constant", constant_values=fill)
    return np.pad(grid, 1, mode=mode)


def moore_neighbour_sum(
    grid: np.ndarray, boundary: BoundaryMode = "fixed", fill: float = 0
) -> np.ndarray:
    """Sum of the 8 surrounding cells (Moore neighbourhood)."""
    p = _pad(grid, boundary, fill)
    h, w = grid.shape
    total = np.zeros(grid.shape, dtype=np.result_type(grid.dtype, np.int16))
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            if dy == 1 and dx == 1:
                continue
            total += p[dy : dy + h, dx : dx + w]
    return total


def von_neumann_neighbour_sum(
    grid: np.ndarray, boundary: BoundaryMode = "fixed", fill: float = 0
) -> np.ndarray:
    """Sum of the 4 orthogonal neighbours (von Neumann neighbourhood)."""
    p = _pad(grid, boundary, fill)
    h, w = grid.shape
    return (
        p[0:h, 1 : w + 1]  # up
        + p[2 : h + 2, 1 : w + 1]  # down
        + p[1 : h + 1, 0:w]  # left
        + p[1 : h + 1, 2 : w + 2]  # right
    )
