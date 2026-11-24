"""Game Theory: a zero-sum game between the player and the difficulty director.

Players and strategies:
- the *player* picks a play style (rows), e.g. ignore Life, plan for it, or
  build for Tetrises;
- the *director* picks a style of Life (columns): a fertility threshold t. The
  LPP (``optimization/adaptive.py``) then sets N so every style has the same
  predicted difficulty. The LPP decides how hard; the director decides which
  kind of hard.

Payoff: the player's survival rate A[i][j] (measured with bots by
``scripts/fit_strategy.py``). The player maximises it, the director minimises
it. The mixed Nash equilibrium of a finite zero-sum game is found by linear
programming. For the director's mix y and game value v:

    minimise v   subject to   sum_j A[i][j] y_j <= v  (every player style i)
                              sum_j y_j = 1,  y >= 0

and symmetrically for the player's mix x (maximise u, sum_i A[i][j] x_i >= u).
By the minimax theorem both LPs give the same v. Sampling its style from y at
every level-up makes the director unexploitable: no player style does better
than v on average, whatever the player does.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from evoltris.config import DirectorStyle, StrategyConfig
from evoltris.optimization.interface import DifficultyProblem, DifficultyVariable
from evoltris.optimization.linprog import LinprogOptimizer
from evoltris.strategy.interface import GameObservation, StrategicAssessment


@dataclass(frozen=True)
class Equilibrium:
    value: float
    """The player's equilibrium survival rate."""
    player_mix: tuple[float, ...]
    director_mix: tuple[float, ...]


def _mix_lp(payoffs: np.ndarray) -> tuple[tuple[float, ...], float]:
    """Mix of the *column* player minimising the row player's best payoff."""
    rows, cols = payoffs.shape
    names = [f"y{j}" for j in range(cols)]
    problem = DifficultyProblem(
        variables=(
            *(DifficultyVariable(n, 0.0, 1.0) for n in names),
            DifficultyVariable("v", -math.inf, math.inf),
        ),
        objective=(*([0.0] * cols), 1.0),
        a_ub=tuple((*map(float, payoffs[i]), -1.0) for i in range(rows)),
        b_ub=(0.0,) * rows,
        a_eq=((*([1.0] * cols), 0.0),),
        b_eq=(1.0,),
    )
    v = LinprogOptimizer().optimize(problem).values
    return tuple(v[n] for n in names), v["v"]


def solve_zero_sum(payoffs: tuple[tuple[float, ...], ...] | np.ndarray) -> Equilibrium:
    """Mixed Nash equilibrium of the zero-sum game (row player maximises)."""
    a = np.asarray(payoffs, dtype=float)
    director, value = _mix_lp(a)
    # The row player's maximin is the column player's minimax on -A^T.
    player, neg_value = _mix_lp(-a.T)
    assert abs(value + neg_value) < 1e-6, "minimax theorem violated"
    return Equilibrium(value, player, director)


class Director:
    """The difficulty director: plays its equilibrium mix of Life styles."""

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        self.equilibrium = solve_zero_sum(config.payoffs)
        self._rng = np.random.default_rng(config.seed)
        self.style: DirectorStyle | None = None
        """The style chosen at the last level-up."""

    def choose(self) -> DirectorStyle:
        p = np.clip(np.asarray(self.equilibrium.director_mix), 0.0, None)
        i = int(self._rng.choice(len(p), p=p / p.sum()))
        self.style = self.config.styles[i]
        return self.style

    def evaluate(self, observation: GameObservation) -> StrategicAssessment:
        """The equilibrium: game value and both mixed strategies."""
        eq = self.equilibrium
        values = {"game_value": eq.value}
        values |= {f"director/{s.name}": p for s, p in zip(self.config.styles, eq.director_mix)}
        values |= {f"player/{n}": p for n, p in zip(self.config.player_styles, eq.player_mix)}
        return StrategicAssessment(values)
