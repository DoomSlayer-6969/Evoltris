"""Measure the Game Theory payoff matrix and solve its equilibrium.

Each director style fixes the fertility threshold t; N is then set by the LPP
so every style has the same predicted difficulty (the stack height of the
default coupling settings). Every bot policy plays --games seeded games against
every style with those fixed settings. The payoff is the survival rate.

    uv run python scripts/fit_strategy.py --games 48

The printed matrix goes into ``StrategyConfig.payoffs`` in ``config.py``.
"""

from __future__ import annotations

import argparse
import dataclasses
from concurrent.futures import ProcessPoolExecutor

from balance_sweep import POLICIES, run_setting

from evoltris.config import AdaptiveConfig, CouplingConfig, StrategyConfig
from evoltris.optimization.adaptive import is_feasible, solve
from evoltris.strategy.director import solve_zero_sum


def style_settings(style_t: float, adaptive: AdaptiveConfig, coupling: CouplingConfig):
    """(N, t) the LPP picks for this style at the default settings' difficulty."""
    target = adaptive.height_model(coupling.locks_per_generation, coupling.fertility_threshold)
    fixed = dataclasses.replace(adaptive, t_bounds=(style_t, style_t))
    return solve(fixed if is_feasible(fixed) else adaptive, target)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--games", type=int, default=48, help="seeds per cell")
    ap.add_argument("--pieces", type=int, default=500, help="piece cap per game")
    args = ap.parse_args()

    strategy, adaptive, base = StrategyConfig(), AdaptiveConfig(), CouplingConfig()
    settings = [style_settings(s.fertility_threshold, adaptive, base) for s in strategy.styles]
    for s, (n, t) in zip(strategy.styles, settings):
        print(f"{s.name:>18}: N={n} t={t:.2f}  predicted height {adaptive.height_model(n, t):.2f}")

    matrix = []
    with ProcessPoolExecutor() as pool:
        for policy in strategy.player_styles:
            assert policy in POLICIES
            row = []
            for n, t in settings:
                coupling = dataclasses.replace(base, locks_per_generation=n, fertility_threshold=t)
                res = run_setting(coupling, policy, args.games, args.pieces, pool=pool)
                row.append(round(1 - sum(r.lost for r in res) / len(res), 3))
            matrix.append(tuple(row))
            print(f"{policy:>10}: " + "  ".join(f"{v:.3f}" for v in row), flush=True)

    eq = solve_zero_sum(matrix)
    print(f"\ngame value (equilibrium survival rate): {eq.value:.3f}")
    print("director mix:", {s.name: round(p, 3) for s, p in zip(strategy.styles, eq.director_mix)})
    print("player mix:  ", dict(zip(strategy.player_styles, (round(p, 3) for p in eq.player_mix))))
    print("\npayoffs = (")
    for row in matrix:
        print(f"    {row},")
    print(")")


if __name__ == "__main__":
    main()
