import dataclasses

import numpy as np
import pytest

from evoltris.config import CMLConfig, CouplingConfig, GameConfig, LifeConfig, TetrisConfig
from evoltris.coupling.board_life import BoardLifeCoupling
from evoltris.coupling.null import NullCoupling
from evoltris.optimization.interface import DifficultyProblem, UndefinedDifficultyOptimizer
from evoltris.sim.world import World
from evoltris.strategy.interface import UndefinedGameTheoryModel


def make_world(**kw):
    cfg = GameConfig(
        tetris=TetrisConfig(seed=0),
        life=LifeConfig(seed=0, step_interval=0.5),
        cml=CMLConfig(seed=0, step_interval=0.25),
        coupling=CouplingConfig(mode="none"),
    )
    return World(dataclasses.replace(cfg, **kw))


def run(world, seconds, dt=1 / 120):
    for _ in range(round(seconds / dt)):
        world.step(dt)


def test_subsystems_step_at_independent_rates():
    w = make_world()
    run(w, 2.0)
    assert w.life.generation == 4
    assert w.cml.steps == 8


def test_disabled_layers_do_not_step():
    w = make_world(life=LifeConfig(enabled=False), cml=CMLConfig(enabled=False))
    run(w, 1.0)
    assert w.life.generation == 0 and w.cml.steps == 0


def test_pause_freezes_everything():
    w = make_world()
    w.paused = True
    life, cml, row = w.life.grid.copy(), w.cml.state.copy(), w.tetris.active.row
    run(w, 1.0)
    np.testing.assert_array_equal(w.life.grid, life)
    np.testing.assert_array_equal(w.cml.state, cml)
    assert w.tetris.active.row == row


def test_null_coupling_keeps_layers_independent():
    w = make_world()
    life_before = w.life.grid.copy()
    w.tetris.hard_drop()
    w.dispatch_lock_events()
    np.testing.assert_array_equal(w.life.grid, life_before)


class RecordingCoupling:
    drives_life = False

    def __init__(self):
        self.locks, self.life_steps, self.cml_steps = [], 0, 0

    def on_piece_locked(self, event, tetris, life, cml):
        self.locks.append(event)

    def on_life_step(self, tetris, life, cml):
        self.life_steps += 1

    def on_cml_step(self, tetris, life, cml):
        self.cml_steps += 1


def test_coupling_hooks_receive_events():
    w = make_world()
    rec = RecordingCoupling()
    w.coupling = rec
    w.tetris.hard_drop()
    run(w, 1.0)
    assert len(rec.locks) == 1
    assert rec.life_steps == 2 and rec.cml_steps == 4


def test_observation_is_a_copy():
    w = make_world()
    obs = w.observation()
    obs.cml_state[:] = 0
    assert w.cml.state.any()


def test_strategy_and_optimizer_stubs_refuse_to_run():
    w = make_world()
    with pytest.raises(NotImplementedError):
        UndefinedGameTheoryModel().evaluate(w.observation())
    with pytest.raises(NotImplementedError):
        UndefinedDifficultyOptimizer().optimize(DifficultyProblem(variables=(), objective=()))


def test_coupling_mode_selects_implementation():
    assert isinstance(make_world().coupling, NullCoupling)
    assert isinstance(World().coupling, BoardLifeCoupling)


def test_board_life_world_does_not_run_free_life_soup():
    w = make_world(coupling=CouplingConfig(mode="board_life"))
    assert w.life.population == 0
    run(w, 2.0)
    assert w.life.generation == 0
    assert w.cml.steps == 8


def test_board_life_world_evolves_board_after_n_locks():
    w = make_world(coupling=CouplingConfig(mode="board_life", locks_per_generation=2))
    w.tetris.hard_drop()
    w.dispatch_lock_events()
    assert w.life.generation == 0
    w.tetris.hard_drop()
    w.dispatch_lock_events()
    assert w.life.generation == 1
    np.testing.assert_array_equal(w.life.grid, (w.tetris.board != 0).astype(np.uint8))
