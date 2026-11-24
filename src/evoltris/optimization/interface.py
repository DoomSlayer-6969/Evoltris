"""Linear Programming difficulty optimizer interface.

A ``DifficultyProblem`` is a solver-agnostic LP; a ``DifficultyOptimizer``
solves it. ``LinprogOptimizer`` (``optimization/linprog.py``) is the
implementation, and ``optimization/adaptive.py`` builds the problem solved at
every level-up. Optimization runs only at level-ups, never every frame.

Standard form:

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
