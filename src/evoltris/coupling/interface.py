"""Interface for interactions between Tetris, Game of Life and CML.

A coupling is the only place where the engines affect one another; the
engines themselves never reference each other. Implementations:

- ``NullCoupling``: no interaction (Life is a free-running overlay).
- ``BoardLifeCoupling``: the Tetris stack is the Life grid and evolves every
  N piece locks, and the CML acts as a fertility mask: only cells whose CML
  value is above a threshold may change in a generation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from evoltris.cml.engine import CMLEngine
    from evoltris.life.engine import LifeEngine
    from evoltris.tetris.engine import LockEvent, TetrisEngine


class BoardCoupling(Protocol):
    drives_life: bool
    """True if the coupling sets the Life grid itself; the World then does not
    seed or time-step the Life engine."""

    def on_start(self, tetris: TetrisEngine, life: LifeEngine, cml: CMLEngine) -> None:
        """Called once by the World after all engines are initialised."""
        ...

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
