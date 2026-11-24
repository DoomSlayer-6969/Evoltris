"""Headless balance sweep: a heuristic bot plays seeded games of Evoltris.

The naive bot ignores Life. The aware bot, on the lock that triggers a
generation, scores each placement on the board that generation would produce.
Each game is capped at --pieces pieces; the CML steps --cml-steps times per
piece (4 is about 1 s per piece at the default 0.25 s CML interval).

    uv run python scripts/balance_sweep.py --games 24

Compares the CML fertility mask off vs on at the default coupling settings.
"""

import argparse

import numpy as np

from evoltris.config import CMLConfig, CouplingConfig, GameConfig, TetrisConfig
from evoltris.sim.world import World
from evoltris.tetris.pieces import ActivePiece



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


def play(seed, fertility, aware, max_pieces=500, cml_steps=4):
    cfg = GameConfig(
        tetris=TetrisConfig(seed=seed),
        cml=CMLConfig(seed=seed),
        coupling=CouplingConfig(fertility_threshold=0.5 if fertility else None),
    )
    w = World(cfg)
    t, cp = w.tetris, w.coupling
    hidden = cfg.board.hidden_rows
    for n in range(max_pieces):
        if t.game_over:
            return n, t.lines, True
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
        for _ in range(cml_steps):
            w.cml.step()
    return max_pieces, t.lines, t.game_over


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--games", type=int, default=24, help="seeds per setting")
    ap.add_argument("--pieces", type=int, default=500, help="piece cap per game")
    ap.add_argument("--cml-steps", type=int, default=4, help="CML steps per piece")
    args = ap.parse_args()
    games = args.games
    for fertility in (False, True):
        for aware in (False, True):
            res = [
                play(s, fertility, aware, args.pieces, args.cml_steps) for s in range(games)
            ]
            losses = sum(r[2] for r in res)
            lpp = sum(r[1] for r in res) / sum(r[0] for r in res)
            print(
                f"fertility={'on ' if fertility else 'off'} {'aware' if aware else 'naive'}: "
                f"{losses}/{games} losses, {lpp:.2f} lines/piece",
                flush=True,
            )


if __name__ == "__main__":
    main()
