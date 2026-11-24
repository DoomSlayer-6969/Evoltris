"""``DifficultyOptimizer`` backed by ``scipy.optimize.linprog`` (HiGHS)."""

from __future__ import annotations

import math

from scipy.optimize import linprog

from evoltris.optimization.interface import DifficultyConfig, DifficultyProblem


class InfeasibleProblem(ValueError):
    """The LP has no solution (constraints cannot all be met within the bounds)."""


class LinprogOptimizer:
    def optimize(self, problem: DifficultyProblem) -> DifficultyConfig:
        c = [-v for v in problem.objective] if problem.maximise else list(problem.objective)
        bounds = [
            (None if math.isinf(v.lower) else v.lower, None if math.isinf(v.upper) else v.upper)
            for v in problem.variables
        ]
        res = linprog(
            c,
            A_ub=problem.a_ub or None,
            b_ub=problem.b_ub or None,
            A_eq=problem.a_eq or None,
            b_eq=problem.b_eq or None,
            bounds=bounds,
            method="highs",
        )
        if not res.success:
            raise InfeasibleProblem(res.message)
        return DifficultyConfig({v.name: float(x) for v, x in zip(problem.variables, res.x)})
