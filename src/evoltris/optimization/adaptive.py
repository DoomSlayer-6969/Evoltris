"""Adaptive difficulty: re-tune the Life coupling at every level-up with an LP.

Decision variables: N = ``locks_per_generation`` and t = ``fertility_threshold``.
Both act through linear models fitted offline from aware-bot sweeps
(``scripts/fit_difficulty.py``):

    height(N, t) = h0 + hN*N + ht*t      mean stack height (rows); higher is harder
    loss(N, t)   = l0 + lN*N + lt*t      share of games the aware bot loses

At each level-up the target difficulty H* moves by ``gain`` per row the
player's average stack height during the level sat below ``comfort_height``
(a low stack means the player is comfortable, so H* rises). H* is clamped to
the heights reachable within the bounds *and* the loss limit, so it cannot
wind up. The LP is

    minimise    s
    subject to  height(N, t) - s <= H*
               -height(N, t) - s <= -H*         (so s >= |height(N, t) - H*|)
                loss(N, t)       <= max_aware_loss
                N, t within bounds,  s >= 0

N must be an integer: the LP relaxation is solved, then re-solved for t with
N fixed to the floor and to the ceiling of its relaxed value, and the better
feasible one is kept. If no setting meets the loss limit, the setting the model
predicts is easiest is used.
"""

from __future__ import annotations

import itertools
import math

from evoltris.config import AdaptiveConfig
from evoltris.optimization.interface import (
    DifficultyOptimizer,
    DifficultyProblem,
    DifficultyVariable,
)
from evoltris.optimization.linprog import InfeasibleProblem, LinprogOptimizer


def build_problem(
    config: AdaptiveConfig,
    target_height: float,
    n_bounds: tuple[int, int] | None = None,
) -> DifficultyProblem:
    """The LP above. ``n_bounds`` overrides ``config.n_bounds`` (used to fix N)."""
    h, loss = config.height_model, config.loss_model
    n_lo, n_hi = n_bounds or config.n_bounds
    t_lo, t_hi = config.t_bounds
    return DifficultyProblem(
        variables=(
            DifficultyVariable("locks_per_generation", n_lo, n_hi),
            DifficultyVariable("fertility_threshold", t_lo, t_hi),
            DifficultyVariable("gap", 0.0, math.inf),
        ),
        objective=(0.0, 0.0, 1.0),
        a_ub=(
            (h.n, h.t, -1.0),
            (-h.n, -h.t, -1.0),
            (loss.n, loss.t, 0.0),
        ),
        b_ub=(
            target_height - h.intercept,
            h.intercept - target_height,
            config.max_aware_loss - loss.intercept,
        ),
    )


def _corners(config: AdaptiveConfig) -> list[tuple[int, float]]:
    return list(itertools.product(config.n_bounds, config.t_bounds))


def _easiest(config: AdaptiveConfig) -> tuple[int, float]:
    return min(_corners(config), key=lambda nt: config.loss_model(*nt))


def fair_height_range(
    config: AdaptiveConfig, optimizer: DifficultyOptimizer | None = None
) -> tuple[float, float]:
    """Lowest and highest predicted height reachable within the bounds and the loss limit.

    Two small LPs (minimise / maximise height). If the loss limit cannot be met,
    both ends are the easiest setting's height.
    """
    opt = optimizer or LinprogOptimizer()
    h, loss = config.height_model, config.loss_model
    ends = []
    for maximise in (False, True):
        problem = DifficultyProblem(
            variables=(
                DifficultyVariable("locks_per_generation", *config.n_bounds),
                DifficultyVariable("fertility_threshold", *config.t_bounds),
            ),
            objective=(h.n, h.t),
            maximise=maximise,
            a_ub=((loss.n, loss.t),),
            b_ub=(config.max_aware_loss - loss.intercept,),
        )
        try:
            v = opt.optimize(problem).values
        except InfeasibleProblem:
            return (h(*_easiest(config)),) * 2
        ends.append(h(v["locks_per_generation"], v["fertility_threshold"]))
    return ends[0], ends[1]


def solve(
    config: AdaptiveConfig,
    target_height: float,
    optimizer: DifficultyOptimizer | None = None,
) -> tuple[int, float]:
    """Integer N and t whose predicted height is closest to the target, subject to the loss limit."""
    opt = optimizer or LinprogOptimizer()
    easiest = _easiest(config)
    try:
        n = opt.optimize(build_problem(config, target_height)).values["locks_per_generation"]
    except InfeasibleProblem:
        return easiest

    # The bounds are integers, so rounding N towards lower predicted loss keeps
    # the relaxed t feasible: at least one of these re-solves succeeds.
    best: tuple[float, int, float] | None = None
    for k in sorted({math.floor(n + 1e-9), math.ceil(n - 1e-9)}):
        try:
            v = opt.optimize(build_problem(config, target_height, (k, k))).values
        except InfeasibleProblem:
            continue
        if best is None or v["gap"] < best[0] - 1e-12:
            best = (v["gap"], k, v["fertility_threshold"])
    return easiest if best is None else (best[1], best[2])


class AdaptiveDifficulty:
    """Tracks the player's stack height and re-tunes (N, t) at each level-up."""

    def __init__(self, config: AdaptiveConfig, n: int, t: float) -> None:
        self.config = config
        self.settings = (n, t)
        self.target_range = fair_height_range(config)
        """Heights the LP can actually reach. Clamping to the fair range (not the
        bounds) stops the target winding up beyond what the loss limit allows."""
        self.target = self._clamp(config.height_model(n, t))
        self._heights: list[int] = []

    def _clamp(self, x: float) -> float:
        lo, hi = self.target_range
        return min(max(x, lo), hi)

    def record_lock(self, stack_height: int) -> None:
        self._heights.append(stack_height)

    @property
    def player_height(self) -> float | None:
        """The player's mean stack height over the current level so far."""
        return sum(self._heights) / len(self._heights) if self._heights else None

    def retune(self) -> tuple[int, float]:
        """Update the target from the last level's play and solve for new settings."""
        h = self.player_height
        if h is not None:
            self.target = self._clamp(self.target + self.config.gain * (self.config.comfort_height - h))
        self._heights.clear()
        self.settings = solve(self.config, self.target)
        return self.settings
