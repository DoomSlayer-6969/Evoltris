"""Linear Programming difficulty optimizer interface (stub).

OPEN DESIGN QUESTION: the decision variables, objective function and
constraints have not been established from game requirements. This module
only fixes the shape of the problem so that a solver (e.g.
``scipy.optimize.linprog``) can be plugged in later. Optimization runs
outside the real-time game loop, between rounds or levels.

Standard form expected of an implementation:

    minimise / maximise   c^T x
    subject to            A_ub x <= b_ub,   A_eq x = b_eq,   l <= x <= u
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class DifficultyVariable:
    name: str
    lower: float
    upper: float


@dataclass(frozen=True)
class DifficultyProblem:
    variables: tuple[DifficultyVariable, ...]
    objective: tuple[float, ...]
    maximise: bool = False
    a_ub: tuple[tuple[float, ...], ...] = ()
    b_ub: tuple[float, ...] = ()
    a_eq: tuple[tuple[float, ...], ...] = ()
    b_eq: tuple[float, ...] = ()


@dataclass(frozen=True)
class DifficultyConfig:
    values: dict[str, float] = field(default_factory=dict)


class DifficultyOptimizer(Protocol):
    def optimize(self, problem: DifficultyProblem) -> DifficultyConfig: ...


class UndefinedDifficultyOptimizer:
    """Placeholder that refuses to run until the LP formulation is specified."""

    def optimize(self, problem: DifficultyProblem) -> DifficultyConfig:
        raise NotImplementedError(
            "LPP formulation not yet specified: define variables, objective and constraints."
        )
