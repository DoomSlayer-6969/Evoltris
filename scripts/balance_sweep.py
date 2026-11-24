"""Headless balance sweep: a heuristic bot plays seeded games of Evoltris.

Bot policies (``POLICIES``):

- ``naive`` ignores Life.
- ``aware``, on the lock that triggers a generation, scores each placement on
  the board that generation would produce.
- ``cautious`` does that too, and on every other lock averages the raw score
  with the score after a hypothetical generation now (keeps the stack Life-proof).
- ``well`` is ``aware`` but keeps the rightmost column open and is rewarded for
  Tetrises (greedy, higher-scoring, riskier).

Each game is capped at --pieces pieces; the CML steps --cml-steps times per
piece (4 is about 1 s per piece at the default 0.25 s CML interval). Games run
in parallel across CPU cores.

    uv run python scripts/balance_sweep.py --table coupling
    uv run python scripts/balance_sweep.py --table fertility

``coupling`` compares coupling settings (fertility mask off, to isolate them);
``fertility`` compares the CML fertility mask off vs on at the default settings.
The LPP optimizer is off unless ``--adaptive`` is given.
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


POLICIES = ("naive", "aware", "cautious", "well")


def well_bonus(board, hidden):
    """``well`` policy: reward Tetrises, penalise filling the rightmost column."""
    v = board[hidden:] != 0
    lines = int(v.all(axis=1).sum())
    return (2.0 if lines >= 4 else 0.0) - 0.4 * int(v[~v.all(axis=1), -1].sum())


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
    policy: str,
    coupling: CouplingConfig,
    max_pieces: int = 500,
    cml_steps: int = 4,
    adaptive: bool = False,
) -> GameResult:
    """One game with the given bot ``policy``. ``adaptive=False`` keeps the settings fixed."""
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}, expected one of {POLICIES}")
    cfg = GameConfig(
        tetris=TetrisConfig(seed=seed),
        cml=CMLConfig(seed=seed),
        coupling=coupling,
        adaptive=AdaptiveConfig(enabled=adaptive),
    )
    w = World(cfg)
    t, cp = w.tetris, w.coupling
    hidden = cfg.board.hidden_rows
    heights = []
    for n in range(max_pieces):
        if t.game_over:
            return GameResult(n, t.lines, True, float(np.mean(heights or [0])))
        has_life = hasattr(cp, "preview")  # NullCoupling: Life never touches the board
        due = has_life and cp.locks_until_generation == 1
        best, best_v = None, -1e18
        saved_active = t.active

        def after_generation(b):
            saved = t.board
            t.board, t.active = b, None
            out = cp.preview(t)
            t.board, t.active = saved, saved_active
            return out

        for cand in placements(t):
            b = t.board.copy()
            for r, c in cand.cells():
                b[r, c] = int(cand.type)
            if policy != "naive" and due:
                v = evaluate(after_generation(b), hidden)
            elif policy == "cautious" and has_life:
                v = 0.5 * evaluate(b, hidden) + 0.5 * evaluate(after_generation(b), hidden)
            else:
                v = evaluate(b, hidden)
            if policy == "well":
                v += well_bonus(b, hidden)
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
    policy: str,
    games: int,
    max_pieces: int = 500,
    cml_steps: int = 4,
    pool: ProcessPoolExecutor | None = None,
    adaptive: bool = False,
) -> list[GameResult]:
    """Play seeds 0..games-1 at one setting, in parallel if ``pool`` is given."""
    jobs = [(s, policy, coupling, max_pieces, cml_steps, adaptive) for s in range(games)]
    if pool is None:
        return [_play_args(j) for j in jobs]
    return list(pool.map(_play_args, jobs))


def summarise(res: list[GameResult]) -> str:
    losses = sum(r.lost for r in res)
    lpp = sum(r.lines for r in res) / sum(r.pieces for r in res)
    height = np.mean([r.mean_height for r in res])
    return f"{losses}/{len(res)} losses, {lpp:.2f} lines/piece, mean height {height:.1f}"


def _coupling(**kw) -> CouplingConfig:
    return dataclasses.replace(CouplingConfig(), **kw)


TABLES: dict[str, list[tuple[str, CouplingConfig]]] = {
    "coupling": [
        ("No Life (mode none)", _coupling(mode="none")),
        (
            "Whole board, no settling, N=5",
            _coupling(locks_per_generation=5, surface_depth=None, settle="none", fertility_threshold=None),
        ),
        (
            "Whole board, column settling, N=5",
            _coupling(locks_per_generation=5, surface_depth=None, settle="columns", fertility_threshold=None),
        ),
        ("Depth 1, cluster settling, N=8", _coupling(fertility_threshold=None)),
        ("Depth 1, cluster settling, N=5", _coupling(locks_per_generation=5, fertility_threshold=None)),
        ("Depth 1, cluster settling, N=12", _coupling(locks_per_generation=12, fertility_threshold=None)),
    ],
    "fertility": [
        ("Fertility mask off", _coupling(fertility_threshold=None)),
        ("Fertility mask on (0.5)", _coupling()),
    ],
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--table", choices=sorted(TABLES), default="fertility")
    ap.add_argument("--games", type=int, default=24, help="seeds per setting")
    ap.add_argument("--pieces", type=int, default=500, help="piece cap per game")
    ap.add_argument("--cml-steps", type=int, default=4, help="CML steps per piece")
    ap.add_argument(
        "--adaptive", action="store_true", help="keep the LPP optimizer on (default: fixed settings)"
    )
    ap.add_argument("--policies", nargs="+", choices=POLICIES, default=["naive", "aware"])
    args = ap.parse_args()
    with ProcessPoolExecutor() as pool:
        for label, coupling in TABLES[args.table]:
            for policy in args.policies:
                res = run_setting(
                    coupling, policy, args.games, args.pieces, args.cml_steps, pool, args.adaptive
                )
                print(f"{label} | {policy}: {summarise(res)}", flush=True)


if __name__ == "__main__":
    main()
