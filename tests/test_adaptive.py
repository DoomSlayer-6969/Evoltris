import dataclasses

import pytest

from evoltris.config import AdaptiveConfig, CouplingConfig, GameConfig, LinearModel, TetrisConfig
from evoltris.optimization.adaptive import (
    AdaptiveDifficulty,
    build_problem,
    fair_height_range,
    solve,
)
from evoltris.optimization.interface import DifficultyProblem, DifficultyVariable
from evoltris.optimization.linprog import InfeasibleProblem, LinprogOptimizer
from evoltris.sim.world import World

# Synthetic model: higher N or t is easier (lower stack, fewer losses).
HEIGHT = LinearModel(intercept=14.0, n=-0.5, t=-5.0)
LOSS = LinearModel(intercept=1.0, n=-0.08, t=-0.6)
CFG = AdaptiveConfig(
    height_model=HEIGHT,
    loss_model=LOSS,
    n_bounds=(4, 12),
    t_bounds=(0.3, 0.7),
    max_aware_loss=0.25,
    comfort_height=8.0,
    gain=0.5,
)


# ------------------------------------------------------------------ linprog


def test_linprog_solves_a_textbook_lp():
    inf = float("inf")
    problem = DifficultyProblem(
        variables=(DifficultyVariable("x", 0, inf), DifficultyVariable("y", 0, inf)),
        objective=(1.0, 1.0),
        maximise=True,
        a_ub=((1.0, 2.0), (3.0, 1.0)),
        b_ub=(4.0, 6.0),
    )
    v = LinprogOptimizer().optimize(problem).values
    assert v["x"] == pytest.approx(1.6) and v["y"] == pytest.approx(1.2)


def test_linprog_reports_infeasibility():
    problem = DifficultyProblem(
        variables=(DifficultyVariable("x", 0, 1),), objective=(1.0,), a_ub=((-1.0,),), b_ub=(-2.0,)
    )
    with pytest.raises(InfeasibleProblem):
        LinprogOptimizer().optimize(problem)


# -------------------------------------------------------------------- solve


def test_build_problem_gap_is_the_absolute_height_error():
    p = build_problem(CFG, target_height=8.0)
    v = LinprogOptimizer().optimize(p).values
    n, t = v["locks_per_generation"], v["fertility_threshold"]
    assert v["gap"] == pytest.approx(abs(HEIGHT(n, t) - 8.0), abs=1e-9)


def test_solve_hits_reachable_target_with_integer_n():
    n, t = solve(CFG, target_height=HEIGHT(7, 0.5))
    assert isinstance(n, int) and CFG.n_bounds[0] <= n <= CFG.n_bounds[1]
    assert CFG.t_bounds[0] <= t <= CFG.t_bounds[1]
    assert HEIGHT(n, t) == pytest.approx(HEIGHT(7, 0.5), abs=1e-6)
    assert LOSS(n, t) <= CFG.max_aware_loss + 1e-9


def test_loss_limit_stops_the_hardest_settings():
    hardest = HEIGHT(4, 0.3)
    assert LOSS(4, 0.3) > CFG.max_aware_loss
    n, t = solve(CFG, target_height=hardest)
    assert LOSS(n, t) <= CFG.max_aware_loss + 1e-9
    assert HEIGHT(n, t) < hardest


def test_unreachable_loss_limit_falls_back_to_easiest_setting():
    cfg = dataclasses.replace(CFG, max_aware_loss=-1.0)
    assert solve(cfg, target_height=10.0) == (12, 0.7)


# --------------------------------------------------------------- controller


def test_comfortable_player_gets_harder_settings():
    d = AdaptiveDifficulty(CFG, n=8, t=0.5)
    before = HEIGHT(*d.settings)
    for _ in range(30):
        d.record_lock(2)  # far below comfort height
    n, t = d.retune()
    assert HEIGHT(n, t) > before
    assert d.player_height is None  # reset for the next level


def test_struggling_player_gets_easier_settings():
    d = AdaptiveDifficulty(CFG, n=8, t=0.5)
    before = HEIGHT(*d.settings)
    for _ in range(30):
        d.record_lock(16)
    n, t = d.retune()
    assert HEIGHT(n, t) < before


def test_target_is_clamped_to_reachable_range():
    d = AdaptiveDifficulty(CFG, n=8, t=0.5)
    for _ in range(20):
        d.record_lock(0)
        d.retune()
    assert d.target == pytest.approx(d.target_range[1])
    d.record_lock(20)
    d.retune()
    assert d.target < d.target_range[1]  # one bad level already pulls it down


def test_retune_without_data_keeps_target():
    d = AdaptiveDifficulty(CFG, n=8, t=0.5)
    target = d.target
    d.retune()
    assert d.target == target


# -------------------------------------------------------------------- world


def make_world(**kw):
    cfg = GameConfig(tetris=TetrisConfig(seed=0), adaptive=CFG)
    return World(dataclasses.replace(cfg, **kw))


def test_level_up_retunes_the_coupling():
    w = make_world()
    assert w.difficulty is not None
    for _ in range(3):
        w.tetris.hard_drop()
        w.dispatch_lock_events()
    w.tetris.lines = w.tetris.config.lines_per_level  # next lock sees a new level
    w.tetris.hard_drop()
    w.dispatch_lock_events()
    n, t = w.difficulty.settings
    assert (w.coupling.config.locks_per_generation, w.coupling.config.fertility_threshold) == (n, t)
    assert HEIGHT(n, t) > HEIGHT(8, 0.5)  # low stack so far: harder


def test_no_retune_without_level_up():
    w = make_world()
    before = w.coupling.config
    for _ in range(3):
        w.tetris.hard_drop()
        w.dispatch_lock_events()
    assert w.coupling.config == before


def test_adaptive_needs_board_life_with_fertility():
    assert make_world(adaptive=dataclasses.replace(CFG, enabled=False)).difficulty is None
    assert make_world(coupling=CouplingConfig(mode="none")).difficulty is None
    assert make_world(coupling=CouplingConfig(fertility_threshold=None)).difficulty is None


def test_fair_range_respects_the_loss_limit():
    lo, hi = fair_height_range(CFG)
    assert lo == pytest.approx(HEIGHT(12, 0.7))
    assert hi < HEIGHT(4, 0.3)  # the unconstrained hardest corner is unfair
    # Highest fair height: N carries the loss reduction (better loss per row), t = 0.3.
    assert hi == pytest.approx(HEIGHT((0.75 - 0.6 * 0.3) / 0.08, 0.3))


def test_one_bad_level_after_strong_play_eases_immediately():
    d = AdaptiveDifficulty(CFG, n=8, t=0.5)
    for _ in range(10):  # strong player: target pinned at the fair maximum
        d.record_lock(0)
        d.retune()
    hardest = HEIGHT(*d.settings)
    d.record_lock(CFG.comfort_height + 2)
    assert HEIGHT(*d.retune()) < hardest
