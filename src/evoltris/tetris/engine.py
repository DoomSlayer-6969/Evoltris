"""Tetris engine: the playable foundation of Evoltris.

The board is an ``np.uint8`` array of shape (total_height, width). Row 0 is the
top; the first ``hidden_rows`` rows are a spawn buffer above the visible
field. Cell value 0 is empty, 1..7 is the ``PieceType`` that locked there.

The engine is time-driven through ``update(dt)`` and has no rendering or
input-device dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from evoltris.config import BoardConfig, TetrisConfig
from evoltris.tetris.pieces import SHAPES, ActivePiece, PieceType, kicks_for
from evoltris.tetris.randomizer import BagRandomizer


@dataclass(frozen=True)
class LockEvent:
    """Emitted every time a piece locks. Consumed by couplings and scoring hooks."""

    piece: PieceType
    cells: tuple[tuple[int, int], ...]
    cleared_rows: tuple[int, ...]
    """Board row indices (before removal) that were cleared."""


class TetrisEngine:
    PREVIEW = 3

    def __init__(
        self, board: BoardConfig | None = None, config: TetrisConfig | None = None
    ) -> None:
        self.board_config = board or BoardConfig()
        self.config = config or TetrisConfig()
        self.board = np.zeros(
            (self.board_config.total_height, self.board_config.width), dtype=np.uint8
        )
        self.randomizer = BagRandomizer(self.config.seed)
        self.active: ActivePiece | None = None
        self.score = 0
        self.lines = 0
        self.game_over = False
        self.soft_dropping = False
        self._gravity_timer = 0.0
        self._lock_timer = 0.0
        self._lock_resets = 0
        self._events: list[LockEvent] = []
        self.spawn()

    # ------------------------------------------------------------------ state

    @property
    def level(self) -> int:
        return self.lines // self.config.lines_per_level

    @property
    def gravity_interval(self) -> float:
        c = self.config
        return max(c.min_gravity_interval, c.base_gravity_interval * c.gravity_decay**self.level)

    @property
    def next_pieces(self) -> list[PieceType]:
        return self.randomizer.peek(self.PREVIEW)

    def drain_events(self) -> list[LockEvent]:
        events, self._events = self._events, []
        return events

    def fits(self, piece: ActivePiece) -> bool:
        h, w = self.board.shape
        for r, c in piece.cells():
            if not (0 <= r < h and 0 <= c < w) or self.board[r, c]:
                return False
        return True

    def is_grounded(self) -> bool:
        return self.active is not None and not self.fits(self.active.moved(d_row=1))

    def ghost(self) -> ActivePiece | None:
        if self.active is None:
            return None
        g = self.active
        while self.fits(g.moved(d_row=1)):
            g = g.moved(d_row=1)
        return g

    # ---------------------------------------------------------------- actions

    def spawn(self, piece_type: PieceType | None = None) -> bool:
        t = piece_type if piece_type is not None else self.randomizer.next()
        size = SHAPES[t].size
        col = (self.board_config.width - size) // 2
        piece = ActivePiece(t, 0, 0, col)
        self._gravity_timer = 0.0
        self._lock_timer = 0.0
        self._lock_resets = 0
        if not self.fits(piece):
            self.active = None
            self.game_over = True
            return False
        self.active = piece
        return True

    def _after_successful_manipulation(self) -> None:
        if self._lock_resets < self.config.max_lock_resets:
            self._lock_timer = 0.0
            self._lock_resets += 1

    def move(self, d_col: int) -> bool:
        if self.game_over or self.active is None:
            return False
        candidate = self.active.moved(d_col=d_col)
        if self.fits(candidate):
            self.active = candidate
            self._after_successful_manipulation()
            return True
        return False

    def rotate(self, direction: int) -> bool:
        """Rotate clockwise (+1) or counter-clockwise (-1) using SRS wall kicks."""
        if self.game_over or self.active is None:
            return False
        frm = self.active.rotation
        to = (frm + direction) % 4
        for d_row, d_col in kicks_for(self.active.type, frm, to):
            candidate = self.active.rotated(to, d_row, d_col)
            if self.fits(candidate):
                self.active = candidate
                self._after_successful_manipulation()
                return True
        return False

    def soft_drop_step(self) -> bool:
        """Move down one row (player-initiated). Awards soft-drop points."""
        if self.game_over or self.active is None:
            return False
        candidate = self.active.moved(d_row=1)
        if self.fits(candidate):
            self.active = candidate
            self.score += self.config.soft_drop_score
            self._gravity_timer = 0.0
            return True
        return False

    def hard_drop(self) -> LockEvent | None:
        if self.game_over or self.active is None:
            return None
        ghost = self.ghost()
        assert ghost is not None
        self.score += self.config.hard_drop_score * (ghost.row - self.active.row)
        self.active = ghost
        return self.lock()

    def lock(self) -> LockEvent | None:
        if self.active is None:
            return None
        piece = self.active
        cells = tuple(piece.cells())
        for r, c in cells:
            self.board[r, c] = int(piece.type)
        self.active = None

        cleared = self.clear_full_rows()
        if cleared:
            n = len(cleared)
            self.score += self.config.line_clear_scores[min(n, 4) - 1] * (self.level + 1)
            self.lines += n

        event = LockEvent(piece.type, cells, cleared)
        self._events.append(event)

        # Lock out: the piece settled entirely within the hidden spawn rows.
        hidden = self.board_config.hidden_rows
        if not cleared and all(r < hidden for r, _ in cells):
            self.game_over = True
            return event
        self.spawn()
        return event

    def clear_full_rows(self) -> tuple[int, ...]:
        full = np.flatnonzero(self.board.all(axis=1))
        if full.size == 0:
            return ()
        keep = self.board[~self.board.all(axis=1)]
        new = np.zeros_like(self.board)
        new[self.board.shape[0] - keep.shape[0] :] = keep
        self.board = new
        return tuple(int(r) for r in full)

    # ------------------------------------------------------------------- time

    def update(self, dt: float) -> None:
        """Advance gravity and lock delay by ``dt`` seconds."""
        if self.game_over or self.active is None:
            return
        if self.is_grounded():
            self._lock_timer += dt
            if self._lock_timer >= self.config.lock_delay:
                self.lock()
            return
        self._lock_timer = 0.0
        self._gravity_timer += dt
        interval = self.gravity_interval
        while self._gravity_timer >= interval and self.active is not None:
            self._gravity_timer -= interval
            if self.fits(self.active.moved(d_row=1)):
                self.active = self.active.moved(d_row=1)
            else:
                break
