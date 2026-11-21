"""Interface for interactions between Tetris, Game of Life and CML.

OPEN DESIGN QUESTION: the rule linking the Game of Life generations, the CML
environment and the Tetris board has not been decided yet. This protocol
defines *where* such a rule plugs in, so that the engines themselves never
reference one another. Until a rule is specified, ``NullCoupling`` is used.

Possible candidates (none implemented; to be decided by the designer):
- treat locked blocks as live cells and run a generation every N locks;
- let GoL live cells act as obstacles on the Tetris board;
- let CML values modulate GoL step frequency or Tetris gravity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from evoltris.cml.engine import CMLEngine
    from evoltris.life.engine import LifeEngine
    from evoltris.tetris.engine import LockEvent, TetrisEngine


class BoardCoupling(Protocol):
    def on_piece_locked(
        self, event: LockEvent, tetris: TetrisEngine, life: LifeEngine, cml: CMLEngine
    ) -> None:
        """Called after a piece locks and lines have been cleared."""
        ...

    def on_life_step(self, tetris: TetrisEngine, life: LifeEngine, cml: CMLEngine) -> None:
        """Called after each Game of Life generation."""
        ...

    def on_cml_step(self, tetris: TetrisEngine, life: LifeEngine, cml: CMLEngine) -> None:
        """Called after each CML step."""
        ...
