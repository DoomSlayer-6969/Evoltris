"""Coupled Map Lattice engine: the continuous environmental layer.

Update rule (diffusive / Kaneko coupling, von Neumann neighbourhood):

    x'_ij = (1 - eps) * f(x_ij) + (eps / 4) * sum_{k in N(i,j)} f(x_k)

where f is the local map and eps the coupling strength. Boundary handling is
applied to the f-values, so ``reflective`` means an edge cell's missing
neighbour contributes its own f-value (no flux across the wall).

This layer is environmental only. It never reads or writes the Game of Life
alive/dead state; any interaction goes through a ``BoardCoupling``.
"""

from __future__ import annotations

import numpy as np

from evoltris.cml.maps import LocalMap, LogisticMap
from evoltris.config import BoundaryMode, CMLConfig
from evoltris.core.grid import von_neumann_neighbour_sum


def cml_step(
    state: np.ndarray, local_map: LocalMap, coupling: float, boundary: BoundaryMode
) -> np.ndarray:
    """Return the next lattice state. Pure function."""
    fx = local_map(state)
    nbr = von_neumann_neighbour_sum(fx, boundary, fill=0.0)
    nxt = (1.0 - coupling) * fx + (coupling / 4.0) * nbr
    # Mathematically within [0,1] already (for "fixed" with fill 0 too, since it only
    # lowers the sum). The clip only removes floating-point drift.
    return np.clip(nxt, 0.0, 1.0)


class CMLEngine:
    def __init__(
        self,
        shape: tuple[int, int],
        config: CMLConfig | None = None,
        local_map: LocalMap | None = None,
    ) -> None:
        self.config = config or CMLConfig()
        self.local_map: LocalMap = local_map or LogisticMap(self.config.r)
        self.state = np.zeros(shape, dtype=np.float64)
        self.steps = 0

    def randomize(self, seed: int | None = None) -> None:
        rng = np.random.default_rng(self.config.seed if seed is None else seed)
        self.state = rng.random(self.state.shape)
        self.steps = 0

    def set_state(self, state: np.ndarray) -> None:
        state = np.asarray(state, dtype=np.float64)
        if state.shape != self.state.shape:
            raise ValueError(f"shape mismatch: {state.shape} != {self.state.shape}")
        if state.min() < 0.0 or state.max() > 1.0:
            raise ValueError("CML state values must lie in [0, 1]")
        self.state = state.copy()

    def step(self) -> None:
        self.state = cml_step(
            self.state, self.local_map, self.config.coupling, self.config.boundary
        )
        self.steps += 1

    @property
    def mean(self) -> float:
        return float(self.state.mean())
