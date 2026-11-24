"""World: owns all engines and advances them on independent fixed timesteps.

Each subsystem has its own accumulator, so the Game of Life and CML can run
at rates independent of Tetris gravity and of the render frame rate.
"""

from __future__ import annotations

import dataclasses

from evoltris.cml.engine import CMLEngine
from evoltris.config import GameConfig
from evoltris.coupling.board_life import BoardLifeCoupling
from evoltris.coupling.interface import BoardCoupling
from evoltris.coupling.null import NullCoupling
from evoltris.life.engine import LifeEngine
from evoltris.optimization.adaptive import AdaptiveDifficulty
from evoltris.strategy.director import Director
from evoltris.strategy.interface import GameObservation
from evoltris.tetris.engine import TetrisEngine


_EPS = 1e-9
"""Tolerance for accumulated floating-point timesteps (e.g. 30 * (1/120) < 0.25)."""


def make_coupling(config: GameConfig) -> BoardCoupling:
    """Build the coupling selected by ``config.coupling.mode``."""
    if config.coupling.mode == "board_life":
        return BoardLifeCoupling(config.coupling, config.board.hidden_rows)
    return NullCoupling()


def make_difficulty(config: GameConfig, coupling: BoardCoupling) -> AdaptiveDifficulty | None:
    """The LPP difficulty controller, if enabled and the coupling has N and t to tune."""
    if not config.adaptive.enabled or not isinstance(coupling, BoardLifeCoupling):
        return None
    c = coupling.config
    if c.fertility_threshold is None:
        return None
    return AdaptiveDifficulty(config.adaptive, c.locks_per_generation, c.fertility_threshold)


class World:
    def __init__(self, config: GameConfig | None = None, coupling: BoardCoupling | None = None):
        self.config = config or GameConfig()
        self.coupling: BoardCoupling = coupling or make_coupling(self.config)
        b = self.config.board
        self.tetris = TetrisEngine(b, self.config.tetris)
        shape = (b.total_height, b.width)
        self.life = LifeEngine(shape, self.config.life)
        self.cml = CMLEngine(shape, self.config.cml)
        if not self.coupling.drives_life:
            self.life.randomize()
        self.cml.randomize()
        self.coupling.on_start(self.tetris, self.life, self.cml)
        self.difficulty = make_difficulty(self.config, self.coupling)
        self.director = (
            Director(self.config.strategy)
            if self.difficulty is not None and self.config.strategy.enabled
            else None
        )
        self._level = self.tetris.level
        self.paused = False
        self.time = 0.0
        self._life_acc = 0.0
        self._cml_acc = 0.0

    def step(self, dt: float) -> None:
        """Advance the world by exactly one fixed timestep ``dt``."""
        if self.paused or self.tetris.game_over:
            return
        self.time += dt

        self.tetris.update(dt)
        self.dispatch_lock_events()

        if self.config.life.enabled and not self.coupling.drives_life:
            self._life_acc += dt
            while self._life_acc >= self.config.life.step_interval - _EPS:
                self._life_acc -= self.config.life.step_interval
                self.life.step()
                self.coupling.on_life_step(self.tetris, self.life, self.cml)

        if self.config.cml.enabled:
            self._cml_acc += dt
            while self._cml_acc >= self.config.cml.step_interval - _EPS:
                self._cml_acc -= self.config.cml.step_interval
                self.cml.step()
                self.coupling.on_cml_step(self.tetris, self.life, self.cml)

    def dispatch_lock_events(self) -> None:
        """Forward lock events (from gravity or player actions) to the coupling."""
        for event in self.tetris.drain_events():
            self.coupling.on_piece_locked(event, self.tetris, self.life, self.cml)
            if self.difficulty is not None:
                self.difficulty.record_lock(self.tetris.stack_height)
                if self.tetris.level > self._level and not self.tetris.game_over:
                    self._retune()
            self._level = self.tetris.level

    def _retune(self) -> None:
        """Level-up: the director picks a style of Life (t), the LPP sets N.

        A new threshold only takes effect at the next fertility snapshot, so the
        current mask (and the G preview) stays valid.
        """
        assert isinstance(self.coupling, BoardLifeCoupling) and self.difficulty is not None
        style = self.director.choose() if self.director is not None else None
        n, t = self.difficulty.retune(style.fertility_threshold if style else None)
        self.coupling.config = dataclasses.replace(
            self.coupling.config, locks_per_generation=n, fertility_threshold=t
        )

    def observation(self) -> GameObservation:
        return GameObservation(
            board=self.tetris.board.copy(),
            life_grid=self.life.grid.copy(),
            cml_state=self.cml.state.copy(),
            score=self.tetris.score,
            lines=self.tetris.lines,
            level=self.tetris.level,
        )
