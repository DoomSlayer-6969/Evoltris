"""Fit the linear difficulty model used by the LPP optimizer.

The aware bot plays --games seeded games at every (N, t) grid point, where
N = locks_per_generation and t = fertility_threshold. Two linear models are
then fitted by least squares:

    height(N, t) = h0 + hN * N + ht * t     mean visible stack height (rows)
    loss(N, t)   = l0 + lN * N + lt * t     fraction of games lost

The printed coefficients go into ``AdaptiveConfig`` in ``config.py``.

    uv run python scripts/fit_difficulty.py --games 24
"""

from __future__ import annotations

import argparse
import dataclasses
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from balance_sweep import run_setting

from evoltris.config import CouplingConfig


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--games", type=int, default=24, help="seeds per grid point")
    ap.add_argument("--pieces", type=int, default=500, help="piece cap per game")
    ap.add_argument("--n", type=int, nargs="+", default=[4, 6, 8, 10, 12])
    ap.add_argument("--t", type=float, nargs="+", default=[0.3, 0.4, 0.5, 0.6, 0.7])
    args = ap.parse_args()

    rows = []
    print(f"{'N':>3} {'t':>5} {'height':>7} {'loss':>6} {'lines/pc':>8}")
    with ProcessPoolExecutor() as pool:
        for n in args.n:
            for t in args.t:
                coupling = dataclasses.replace(
                    CouplingConfig(), locks_per_generation=n, fertility_threshold=t
                )
                res = run_setting(coupling, True, args.games, args.pieces, pool=pool)
                height = float(np.mean([r.mean_height for r in res]))
                loss = sum(r.lost for r in res) / len(res)
                lpp = sum(r.lines for r in res) / sum(r.pieces for r in res)
                rows.append((n, t, height, loss))
                print(f"{n:>3} {t:>5.2f} {height:>7.2f} {loss:>6.2f} {lpp:>8.2f}", flush=True)

    data = np.array(rows)
    x = np.column_stack([np.ones(len(data)), data[:, 0], data[:, 1]])
    for name, col in (("height", 2), ("loss", 3)):
        y = data[:, col]
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        r2 = 1 - ((y - x @ coef) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        print(f"{name}: intercept={coef[0]:.4f} n={coef[1]:.4f} t={coef[2]:.4f}  (R^2={r2:.2f})")


if __name__ == "__main__":
    main()
