"""Headless balance sweep: a heuristic bot plays seeded games of Evoltris.

The naive bot ignores Life. The aware bot, on the lock that triggers a
generation, scores each placement on the board that generation would produce.
Each game is capped at --pieces pieces; the CML steps --cml-steps times per
piece (4 is about 1 s per piece at the default 0.25 s CML interval). Games run
in parallel across CPU cores.

    uv run python scripts/balance_sweep.py --games 24

Compares the CML fertility mask off vs on at the default coupling settings.
"""

from __future__ import annotations

import argparse
import dataclasses
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np

from evoltris.config import AdaptiveConfig, CMLConfig, CouplingConfig, GameConfig, TetrisConfig
from evoltris.sim.world import World
from evoltris.tetris.pieces import ActivePiece


@dataclass(frozen=True)
class GameResult:
    pieces: int
    lines: int
    lost: bool
    mean_height: float
    """Visible stack height in rows, averaged over every lock."""


def evaluate(board, hidden):
    v = board[hidden:] != 0
    full = v.all(axis=1)
    lines = int(full.sum())
    v = v[~full]
    h = v.shape[0]
    tops = np.where(v.any(axis=0), v.argmax(axis=0), h)
    heights = h - tops
    holes = sum(int((~v[tops[c]:, c]).sum()) for c in range(v.shape[1]))
    bump = int(np.abs(np.diff(heights)).sum())
    return -0.51 * heights.sum() + 0.76 * lines - 0.36 * holes - 0.18 * bump


def placements(t):
    p = t.active
    for rot in range(4):
        for col in range(-3, t.board.shape[1] + 1):
            cand = ActivePiece(p.type, rot, p.row, col)
            if not t.fits(cand):
                continue
            while t.fits(cand.moved(1)):
                cand = cand.moved(1)
            yield cand


def play(
    seed: int,
    aware: bool,
    coupling: CouplingConfig,
    max_pieces: int = 500,
    cml_steps: int = 4,
) -> GameResult:
    cfg = GameConfig(
        tetris=TetrisConfig(seed=seed),
        cml=CMLConfig(seed=seed),
        coupling=coupling,
        adaptive=AdaptiveConfig(enabled=False),  # measure fixed settings
    )
    w = World(cfg)
    t, cp = w.tetris, w.coupling
    hidden = cfg.board.hidden_rows
    heights = []
    for n in range(max_pieces):
        if t.game_over:
            return GameResult(n, t.lines, True, float(np.mean(heights or [0])))
        due = cp.locks_until_generation == 1
        best, best_v = None, -1e18
        saved_active = t.active
        for cand in placements(t):
            b = t.board.copy()
            for r, c in cand.cells():
                b[r, c] = int(cand.type)
            if aware and due:
                saved = t.board
                t.board, t.active = b, None
                b = cp.preview(t)
                t.board, t.active = saved, saved_active
            v = evaluate(b, hidden)
            if v > best_v:
                best, best_v = cand, v
        t.active = best
        t.hard_drop()
        w.dispatch_lock_events()
        heights.append(t.stack_height)
        for _ in range(cml_steps):
            w.cml.step()
    return GameResult(max_pieces, t.lines, t.game_over, float(np.mean(heights)))


def _play_args(args):
    return play(*args)


def run_setting(
    coupling: CouplingConfig,
    aware: bool,
    games: int,
    max_pieces: int = 500,
    cml_steps: int = 4,
    pool: ProcessPoolExecutor | None = None,
) -> list[GameResult]:
    """Play seeds 0..games-1 at one setting, in parallel if ``pool`` is given."""
    jobs = [(s, aware, coupling, max_pieces, cml_steps) for s in range(games)]
    if pool is None:
        return [_play_args(j) for j in jobs]
    return list(pool.map(_play_args, jobs))


def summarise(res: list[GameResult]) -> str:
    losses = sum(r.lost for r in res)
    lpp = sum(r.lines for r in res) / sum(r.pieces for r in res)
    height = np.mean([r.mean_height for r in res])
    return f"{losses}/{len(res)} losses, {lpp:.2f} lines/piece, mean height {height:.1f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--games", type=int, default=24, help="seeds per setting")
    ap.add_argument("--pieces", type=int, default=500, help="piece cap per game")
    ap.add_argument("--cml-steps", type=int, default=4, help="CML steps per piece")
    args = ap.parse_args()
    with ProcessPoolExecutor() as pool:
        for threshold in (None, 0.5):
            coupling = dataclasses.replace(CouplingConfig(), fertility_threshold=threshold)
            for aware in (False, True):
                res = run_setting(coupling, aware, args.games, args.pieces, args.cml_steps, pool)
                label = f"fertility={'on ' if threshold else 'off'} "
                print(label + f"{'aware' if aware else 'naive'}: {summarise(res)}", flush=True)


if __name__ == "__main__":
    main()
