"""Central configuration for Evoltris.

All tunable mathematical and gameplay constants live here so they are not
scattered through the engines. Every config is a frozen dataclass; build a
modified copy with ``dataclasses.replace``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BoundaryMode = Literal["fixed", "periodic", "reflective"]
"""How neighbourhoods are evaluated at the grid edge.

- ``fixed``: cells outside the grid have a constant value (0 by default).
- ``periodic``: the grid wraps around (torus).
- ``reflective``: the outside neighbour mirrors the edge cell (zero-flux /
  Neumann boundary). For diffusive coupling this means no exchange across
  the wall.
"""


@dataclass(frozen=True)
class BoardConfig:
    width: int = 10
    height: int = 20
    hidden_rows: int = 2
    """Extra rows above the visible field where pieces spawn."""

    @property
    def total_height(self) -> int:
        return self.height + self.hidden_rows


@dataclass(frozen=True)
class TetrisConfig:
    lines_per_level: int = 10
    line_clear_scores: tuple[int, int, int, int] = (100, 300, 500, 800)
    """Base score for clearing 1, 2, 3, 4 lines, multiplied by (level + 1)."""
    soft_drop_score: int = 1
    hard_drop_score: int = 2
    base_gravity_interval: float = 0.8
    """Seconds per row at level 0."""
    gravity_decay: float = 0.85
    """Gravity interval is multiplied by this factor per level."""
    min_gravity_interval: float = 0.05
    lock_delay: float = 0.5
    """Seconds a grounded piece may sit before it locks."""
    max_lock_resets: int = 15
    seed: int | None = None


@dataclass(frozen=True)
class LifeConfig:
    """Conway's Game of Life (B3/S23). The rules themselves are not configurable."""

    boundary: BoundaryMode = "fixed"
    step_interval: float = 0.5
    """Seconds of simulated time between generations."""
    initial_density: float = 0.25
    seed: int | None = None
    enabled: bool = True


@dataclass(frozen=True)
class CMLConfig:
    """Coupled Map Lattice with diffusive (Kaneko) nearest-neighbour coupling.

    x'_ij = (1 - eps) * f(x_ij) + (eps / 4) * sum_{von Neumann nbrs} f(x_nbr)
    with f the local map (logistic: f(x) = r * x * (1 - x)).
    """

    r: float = 3.9
    """Logistic map parameter, must lie in [0, 4] to keep f: [0,1] -> [0,1]."""
    coupling: float = 0.3
    """Coupling strength eps in [0, 1]."""
    boundary: BoundaryMode = "reflective"
    step_interval: float = 0.25
    seed: int | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.r <= 4.0:
            raise ValueError(f"logistic parameter r must be in [0, 4], got {self.r}")
        if not 0.0 <= self.coupling <= 1.0:
            raise ValueError(f"coupling must be in [0, 1], got {self.coupling}")


CouplingMode = Literal["none", "board_life"]
"""How the engines interact.

- ``none``: the engines run independently (Life is a free-running overlay).
- ``board_life``: the Tetris stack *is* the Life grid; a generation is applied
  to the visible board every ``locks_per_generation`` piece locks.
"""


SettleMode = Literal["none", "clusters", "columns"]
"""What happens to blocks left floating after a board generation.

- ``none``: they stay where they are (holes remain).
- ``clusters``: each 4-connected group falls as a rigid body (sticky gravity).
- ``columns``: each column's blocks fall straight down to close its gaps.
"""


@dataclass(frozen=True)
class CouplingConfig:
    mode: CouplingMode = "board_life"
    locks_per_generation: int = 8
    """A Life generation is applied to the board after every N piece locks."""
    boundary: BoundaryMode = "fixed"
    """Boundary used for the board generation (``fixed``: walls and floor are dead)."""
    surface_depth: int | None = 1
    """If set, only cells within this many rows of their column's top surface
    evolve; deeper blocks are frozen (but still count as neighbours).
    ``None`` evolves the whole visible board."""
    settle: SettleMode = "clusters"
    """How floating blocks fall after a generation (see ``SettleMode``).

    Defaults (N=8, depth 1, clusters) were chosen from headless bot sweeps; see
    ``coupling/board_life.py``. Lower N is harder.
    """

    def __post_init__(self) -> None:
        if self.locks_per_generation < 1:
            raise ValueError(
                f"locks_per_generation must be >= 1, got {self.locks_per_generation}"
            )
        if self.surface_depth is not None and self.surface_depth < 1:
            raise ValueError(f"surface_depth must be >= 1 or None, got {self.surface_depth}")


@dataclass(frozen=True)
class InputConfig:
    das: float = 0.17
    """Delayed auto shift: seconds a key is held before auto-repeat starts."""
    arr: float = 0.05
    """Auto repeat rate: seconds between repeats."""
    soft_drop_interval: float = 0.05


@dataclass(frozen=True)
class RenderConfig:
    cell_size: int = 30
    sidebar_width: int = 310
    fps: int = 60
    show_life: bool = True
    show_cml: bool = True


@dataclass(frozen=True)
class GameConfig:
    board: BoardConfig = field(default_factory=BoardConfig)
    tetris: TetrisConfig = field(default_factory=TetrisConfig)
    life: LifeConfig = field(default_factory=LifeConfig)
    cml: CMLConfig = field(default_factory=CMLConfig)
    coupling: CouplingConfig = field(default_factory=CouplingConfig)
    input: InputConfig = field(default_factory=InputConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    sim_dt: float = 1.0 / 120.0
    """Fixed simulation timestep in seconds."""
