"""Board-as-Life coupling: the Tetris stack is the Game of Life grid.

Every ``locks_per_generation`` piece locks, one Conway generation (B3/S23) is
applied to the *visible* part of the board, treating every occupied cell as
alive:

- a block with 2 or 3 occupied neighbours survives and keeps its piece colour;
- any other block dies and leaves a hole;
- an empty cell with exactly 3 occupied neighbours is born as ``GARBAGE``.

Hidden spawn rows are neither evolved nor counted as neighbours, and the
active piece is never overwritten by a birth. With ``surface_depth = K`` only
cells within K rows of their column's top surface (and the air above it) may
change; deeper cells still count as neighbours but are frozen.

Floating blocks can then settle: ``settle = "clusters"`` drops each
4-connected group of blocks as a rigid body until it rests (sticky/cascade
gravity); ``settle = "columns"`` drops every block straight down to close all
gaps in its column. Finally, full rows are cleared and scored like a normal
line clear.

Balance (from headless bot sweeps): without settling, dead blocks leave covered
holes and the stack becomes unplayable; with column settling Life only erodes
and stops mattering. Sticky ``clusters`` settling with ``surface_depth = 1``
punishes players who ignore the next generation and rewards those who plan for
it, with ``locks_per_generation`` acting as a smooth difficulty knob.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

import numpy as np

from evoltris.config import BoundaryMode, CouplingConfig, SettleMode
from evoltris.life.engine import life_step
from evoltris.tetris.pieces import GARBAGE

if TYPE_CHECKING:
    from evoltris.cml.engine import CMLEngine
    from evoltris.life.engine import LifeEngine
    from evoltris.tetris.engine import LockEvent, TetrisEngine


def surface_mask(alive: np.ndarray, depth: int) -> np.ndarray:
    """Cells at most ``depth - 1`` rows below their column's topmost block, plus all air above it.

    An empty column is entirely inside the mask.
    """
    h = alive.shape[0]
    top = np.where(alive.any(axis=0), alive.argmax(axis=0), h)
    return np.arange(h)[:, None] < top[None, :] + depth


def settle_columns(grid: np.ndarray) -> np.ndarray:
    """Drop every block in each column to the bottom, keeping its order and value."""
    out = np.zeros_like(grid)
    h = grid.shape[0]
    for c in range(grid.shape[1]):
        col = grid[:, c]
        blocks = col[col != 0]
        out[h - blocks.size :, c] = blocks
    return out


def _label_clusters(occ: np.ndarray) -> tuple[np.ndarray, int]:
    """4-connected component labels (1..n) of ``occ``; 0 is empty."""
    labels = np.zeros(occ.shape, dtype=np.int32)
    h, w = occ.shape
    n = 0
    for r0, c0 in zip(*np.nonzero(occ)):
        if labels[r0, c0]:
            continue
        n += 1
        labels[r0, c0] = n
        stack = [(int(r0), int(c0))]
        while stack:
            r, c = stack.pop()
            for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= rr < h and 0 <= cc < w and occ[rr, cc] and not labels[rr, cc]:
                    labels[rr, cc] = n
                    stack.append((rr, cc))
    return labels, n


def settle_clusters(grid: np.ndarray) -> np.ndarray:
    """Drop each 4-connected group of blocks as a rigid body until nothing can fall.

    Groups that land on each other merge and keep falling together.
    """
    g = grid.copy()
    h = g.shape[0]
    while True:
        labels, n = _label_clusters(g != 0)
        moved = False
        # Lowest groups first, so groups resting on them see their final position.
        order = sorted(range(1, n + 1), key=lambda k: -np.nonzero(labels == k)[0].max())
        for k in order:
            rows, cols = np.nonzero(labels == k)
            values = g[rows, cols]
            g[rows, cols] = 0
            drop = 0
            while True:
                nr = rows + drop + 1
                if nr.max() >= h or g[nr, cols].any():
                    break
                drop += 1
            g[rows + drop, cols] = values
            if drop:
                labels[rows, cols] = 0
                labels[rows + drop, cols] = k
                moved = True
        if not moved:
            return g


def board_life_step(
    board: np.ndarray,
    hidden_rows: int,
    boundary: BoundaryMode = "fixed",
    protected: Iterable[tuple[int, int]] = (),
    surface_depth: int | None = None,
    settle: SettleMode = "none",
) -> np.ndarray:
    """Return ``board`` after one Life generation on its visible rows.

    Pure function; ``board`` is not modified. ``protected`` cells (board
    coordinates, e.g. the active piece) never receive a birth. If
    ``surface_depth`` is set, only cells inside ``surface_mask`` may change.
    ``settle`` then lets floating visible blocks fall (see module docstring).
    """
    out = board.copy()
    visible = board[hidden_rows:]
    alive = visible != 0
    nxt = life_step(alive.astype(np.uint8), boundary).astype(bool)
    if surface_depth is not None:
        frozen = ~surface_mask(alive, surface_depth)
        nxt[frozen] = alive[frozen]
    born = nxt & ~alive
    for r, c in protected:
        if r >= hidden_rows:
            born[r - hidden_rows, c] = False
    new_visible = np.where(nxt & alive, visible, 0).astype(np.uint8)
    new_visible[born] = GARBAGE
    if settle == "columns":
        new_visible = settle_columns(new_visible)
    elif settle == "clusters":
        new_visible = settle_clusters(new_visible)
    out[hidden_rows:] = new_visible
    return out


class BoardLifeCoupling:
    drives_life = True
    """The Life engine mirrors the board instead of running its own soup."""

    def __init__(self, config: CouplingConfig | None = None, hidden_rows: int = 2) -> None:
        self.config = config or CouplingConfig(mode="board_life")
        self.hidden_rows = hidden_rows
        self.locks_since_generation = 0

    @property
    def locks_until_generation(self) -> int:
        return self.config.locks_per_generation - self.locks_since_generation

    def _protected(self, tetris: TetrisEngine) -> tuple[tuple[int, int], ...]:
        return tuple(tetris.active.cells()) if tetris.active is not None else ()

    def preview(self, tetris: TetrisEngine, settle: bool = True) -> np.ndarray:
        """The board the next generation would produce (before line clears).

        With ``settle=False`` floating blocks are left in place, which shows
        exactly which cells Life itself kills and creates.
        """
        c = self.config
        return board_life_step(
            tetris.board,
            self.hidden_rows,
            c.boundary,
            self._protected(tetris),
            c.surface_depth,
            c.settle if settle else "none",
        )

    def evolve(self, tetris: TetrisEngine, life: LifeEngine) -> tuple[int, ...]:
        """Apply one generation to the board now. Returns the rows it cleared."""
        cleared = tetris.replace_board(self.preview(tetris))
        life.record_generation(tetris.board)
        return cleared

    def on_piece_locked(
        self, event: LockEvent, tetris: TetrisEngine, life: LifeEngine, cml: CMLEngine
    ) -> None:
        if tetris.game_over:
            return
        self.locks_since_generation += 1
        if self.locks_since_generation >= self.config.locks_per_generation:
            self.locks_since_generation = 0
            self.evolve(tetris, life)

    def on_life_step(self, tetris: TetrisEngine, life: LifeEngine, cml: CMLEngine) -> None:
        pass

    def on_cml_step(self, tetris: TetrisEngine, life: LifeEngine, cml: CMLEngine) -> None:
        pass
