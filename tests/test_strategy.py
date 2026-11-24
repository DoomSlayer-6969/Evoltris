import dataclasses

import numpy as np
import pytest

from evoltris.config import (
    AdaptiveConfig,
    DirectorStyle,
    GameConfig,
    LinearModel,
    StrategyConfig,
    TetrisConfig,
)
from evoltris.optimization.adaptive import AdaptiveDifficulty
from evoltris.sim.world import World
from evoltris.strategy.director import Director, solve_zero_sum

STYLES = (DirectorStyle("wide", 0.3), DirectorStyle("narrow", 0.7))
PLAYERS = ("a", "b")


def strategy(payoffs, seed=0):
    return StrategyConfig(styles=STYLES, player_styles=PLAYERS, payoffs=payoffs, seed=seed)


# ------------------------------------------------------------ solve_zero_sum


def test_matching_pennies_mixes_evenly():
    eq = solve_zero_sum(((1.0, 0.0), (0.0, 1.0)))
    assert eq.value == pytest.approx(0.5)
    assert eq.player_mix == pytest.approx((0.5, 0.5))
    assert eq.director_mix == pytest.approx((0.5, 0.5))


def test_rock_paper_scissors_is_uniform():
    rps = ((0.5, 0.0, 1.0), (1.0, 0.5, 0.0), (0.0, 1.0, 0.5))  # win 1, draw 0.5, lose 0
    eq = solve_zero_sum(rps)
    assert eq.value == pytest.approx(0.5)
    assert eq.player_mix == pytest.approx((1 / 3,) * 3)
    assert eq.director_mix == pytest.approx((1 / 3,) * 3)


def test_saddle_point_gives_pure_strategies():
    # Row 0 dominates; against it the director's column 1 is worse for the player.
    eq = solve_zero_sum(((0.9, 0.8), (0.5, 0.4)))
    assert eq.value == pytest.approx(0.8)
    assert eq.player_mix == pytest.approx((1.0, 0.0))
    assert eq.director_mix == pytest.approx((0.0, 1.0))


@pytest.mark.parametrize("seed", range(5))
def test_equilibrium_satisfies_minimax(seed):
    a = np.random.default_rng(seed).random((4, 3))
    eq = solve_zero_sum(a)
    x, y = np.array(eq.player_mix), np.array(eq.director_mix)
    assert x.sum() == pytest.approx(1) and y.sum() == pytest.approx(1)
    assert (x >= -1e-9).all() and (y >= -1e-9).all()
    # No player style beats v against y; no director style holds the player below v against x.
    assert (a @ y).max() == pytest.approx(eq.value, abs=1e-7)
    assert (x @ a).min() == pytest.approx(eq.value, abs=1e-7)


# ------------------------------------------------------------------ director


def test_director_samples_its_equilibrium_mix():
    d = Director(strategy(((1.0, 0.0), (0.0, 1.0))))
    picks = [d.choose().name for _ in range(2000)]
    assert picks.count("wide") / len(picks) == pytest.approx(0.5, abs=0.05)
    assert d.style.name == picks[-1]


def test_director_plays_pure_strategy_at_saddle_point():
    d = Director(strategy(((0.9, 0.8), (0.5, 0.4))))
    assert {d.choose().name for _ in range(50)} == {"narrow"}


def test_director_is_reproducible_with_a_seed():
    a, b = (Director(strategy(((1.0, 0.0), (0.0, 1.0)), seed=7)) for _ in range(2))
    assert [a.choose() for _ in range(20)] == [b.choose() for _ in range(20)]


def test_evaluate_reports_equilibrium():
    w = World(GameConfig(tetris=TetrisConfig(seed=0)))
    values = Director(strategy(((1.0, 0.0), (0.0, 1.0)))).evaluate(w.observation()).values
    assert values["game_value"] == pytest.approx(0.5)
    assert values["director/wide"] == pytest.approx(0.5)
    assert values["player/a"] == pytest.approx(0.5)


def test_payoff_shape_is_validated():
    with pytest.raises(ValueError):
        strategy(((1.0, 0.0),))
    with pytest.raises(ValueError):
        strategy(((1.0,), (0.0,)))


# ------------------------------------------------- LPP with the director's t

HEIGHT = LinearModel(intercept=14.0, n=-0.5, t=-5.0)
LOSS = LinearModel(intercept=1.0, n=-0.08, t=-0.6)
ADAPTIVE = AdaptiveConfig(
    height_model=HEIGHT, loss_model=LOSS, n_bounds=(4, 12), t_bounds=(0.3, 0.7), max_aware_loss=0.25
)


def test_retune_fixes_t_to_the_directors_choice():
    d = AdaptiveDifficulty(ADAPTIVE, n=8, t=0.5)
    target = d.target
    n, t = d.retune(0.7)
    assert t == pytest.approx(0.7)
    assert abs(HEIGHT(n, t) - target) <= 0.5 / 2 + 1e-9  # best integer N: within half a step


def test_unfair_director_choice_is_overruled():
    cfg = dataclasses.replace(ADAPTIVE, n_bounds=(4, 6))  # at t = 0.3, even N = 6 loses 34%
    d = AdaptiveDifficulty(cfg, n=5, t=0.7)
    n, t = d.retune(0.3)
    assert t != pytest.approx(0.3)
    assert LOSS(n, t) <= cfg.max_aware_loss + 1e-9


# --------------------------------------------------------------------- world


def make_world(**kw):
    cfg = GameConfig(
        tetris=TetrisConfig(seed=0),
        strategy=strategy(((0.9, 0.8), (0.5, 0.4))),  # director always picks "narrow"
    )
    return World(dataclasses.replace(cfg, **kw))


def test_level_up_applies_the_directors_style():
    w = make_world()
    assert w.director is not None and w.director.style is None
    w.tetris.lines = w.tetris.config.lines_per_level
    w.tetris.hard_drop()
    w.dispatch_lock_events()
    assert w.director.style.name == "narrow"
    assert w.coupling.config.fertility_threshold == pytest.approx(0.7)
    assert w.coupling.config.locks_per_generation == w.difficulty.settings[0]


def test_director_needs_the_adaptive_lpp():
    assert make_world(strategy=dataclasses.replace(StrategyConfig(), enabled=False)).director is None
    assert make_world(adaptive=AdaptiveConfig(enabled=False)).director is None
