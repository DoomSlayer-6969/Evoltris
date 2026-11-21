"""No-op coupling: the engines run independently. Default until a rule is designed."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evoltris.cml.engine import CMLEngine
    from evoltris.life.engine import LifeEngine
    from evoltris.tetris.engine import LockEvent, TetrisEngine


class NullCoupling:
    def on_piece_locked(
        self, event: LockEvent, tetris: TetrisEngine, life: LifeEngine, cml: CMLEngine
    ) -> None:
        pass

    def on_life_step(self, tetris: TetrisEngine, life: LifeEngine, cml: CMLEngine) -> None:
        pass

    def on_cml_step(self, tetris: TetrisEngine, life: LifeEngine, cml: CMLEngine) -> None:
        pass
