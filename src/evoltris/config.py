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
    fertility_threshold: float | None = 0.5
    """CML fertility mask. If set (and the CML is enabled), a generation may only
    change cells whose CML value exceeded this threshold when the mask was last
    snapshotted (at game start and right after each generation). ``None`` lets
    every cell evolve."""

    def __post_init__(self) -> None:
        if self.fertility_threshold is not None and not 0.0 <= self.fertility_threshold <= 1.0:
            raise ValueError(
                f"fertility_threshold must be in [0, 1] or None, got {self.fertility_threshold}"
            )
        if self.locks_per_generation < 1:
            raise ValueError(
                f"locks_per_generation must be >= 1, got {self.locks_per_generation}"
            )
        if self.surface_depth is not None and self.surface_depth < 1:
            raise ValueError(f"surface_depth must be >= 1 or None, got {self.surface_depth}")


@dataclass(frozen=True)
class LinearModel:
    """y = intercept + n * locks_per_generation + t * fertility_threshold."""

    intercept: float
    n: float
    t: float

    def __call__(self, n: float, t: float) -> float:
        return self.intercept + self.n * n + self.t * t


@dataclass(frozen=True)
class AdaptiveConfig:
    """LPP difficulty optimizer: re-tunes N and t at every level-up.

    Only active with the ``board_life`` coupling and a fertility threshold.
    See ``optimization/adaptive.py`` for the LP.
    """

    enabled: bool = True
    n_bounds: tuple[int, int] = (4, 12)
    """Range of ``locks_per_generation``."""
    t_bounds: tuple[float, float] = (0.3, 0.7)
    """Range of ``fertility_threshold``."""
    max_aware_loss: float = 0.5
    """Fairness constraint: predicted aware-bot loss rate must stay at or below this.

    Tighter limits narrow the fair range (0.25 allows only N >= ~10); wider ones
    allow bigger level-to-level swings and punish ignoring Life more. With 0.5
    the optimizer uses N in 7..12 and the aware bot still loses ~5/24 games."""
    comfort_height: float = 7.0
    """Average stack height (rows) the controller steers the player towards."""
    gain: float = 0.5
    """Rows of target bot height per row the player's stack sat below comfort."""
    height_model: LinearModel = LinearModel(intercept=10.2696, n=-0.2205, t=-1.8127)
    """Aware-bot mean stack height. Fitted by ``scripts/fit_difficulty.py``
    (24 games per point, N in 4..12, t in 0.3..0.7, R^2 = 0.83)."""
    loss_model: LinearModel = LinearModel(intercept=0.9550, n=-0.0538, t=-0.3000)
    """Aware-bot loss rate (500-piece cap). Same fit, R^2 = 0.83."""

    def __post_init__(self) -> None:
        if not self.n_bounds[0] <= self.n_bounds[1] or self.n_bounds[0] < 1:
            raise ValueError(f"invalid n_bounds {self.n_bounds}")
        if not 0.0 <= self.t_bounds[0] <= self.t_bounds[1] <= 1.0:
            raise ValueError(f"invalid t_bounds {self.t_bounds}")


@dataclass(frozen=True)
class DirectorStyle:
    """A kind of Life the director can choose; the LPP then sets N for this t."""

    name: str
    fertility_threshold: float


@dataclass(frozen=True)
class StrategyConfig:
    """Game Theory director: a zero-sum game between player and director.

    Rows are player styles (bot policies), columns are director styles, entries
    are the player's survival rate. At each level-up the director samples a
    style from its mixed Nash equilibrium; see ``strategy/director.py``.
    Requires the adaptive LPP (it picks t, the LPP then picks N).
    """

    enabled: bool = True
    styles: tuple[DirectorStyle, ...] = (
        DirectorStyle("rare & wide", 0.3),
        DirectorStyle("balanced", 0.5),
        DirectorStyle("frequent & narrow", 0.7),
    )
    player_styles: tuple[str, ...] = ("naive", "aware", "cautious", "well")
    payoffs: tuple[tuple[float, ...], ...] = (
        (0.250, 0.146, 0.146),
        (0.792, 0.646, 0.604),
        (0.000, 0.000, 0.042),
        (0.146, 0.104, 0.062),
    )
    """Survival rate of each player style (row) against each director style
    (column), each at the default settings' predicted difficulty. Measured by
    ``scripts/fit_strategy.py`` (48 games per cell, so about +/-0.07 noise).
    ``aware`` dominates, so the equilibrium is pure: the director always plays
    "frequent & narrow" (game value 0.604)."""
    seed: int | None = None
    """Seed for the director's random style choice."""

    def __post_init__(self) -> None:
        if len(self.payoffs) != len(self.player_styles) or any(
            len(row) != len(self.styles) for row in self.payoffs
        ):
            raise ValueError("payoffs must have one row per player style, one column per style")
        for s in self.styles:
            if not 0.0 <= s.fertility_threshold <= 1.0:
                raise ValueError(f"style {s.name!r}: threshold must be in [0, 1]")


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
    adaptive: AdaptiveConfig = field(default_factory=AdaptiveConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    input: InputConfig = field(default_factory=InputConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    sim_dt: float = 1.0 / 120.0
    """Fixed simulation timestep in seconds."""
