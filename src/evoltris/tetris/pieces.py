"""Tetromino definitions using the Super Rotation System (SRS).

Coordinates are (row, col) inside the piece's bounding box, with rows growing
downward (screen convention). Rotation states 0, R, 2, L are indexed 0..3 and
are produced by rotating the spawn state clockwise inside the box, which
matches the SRS reference states.

SRS kick tables are published with +y pointing *up*; they are converted here
to (d_row, d_col) with rows pointing down.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class PieceType(IntEnum):
    """Board cell values: 0 is empty, 1..7 identify the locked piece type.

    ``GARBAGE`` (8) marks cells that were not placed by the player but born
    from a Game of Life generation.
    """

    I = 1
    O = 2
    T = 3
    S = 4
    Z = 5
    J = 6
    L = 7


GARBAGE = 8
"""Board cell value for blocks born from a Game of Life generation."""


Cells = tuple[tuple[int, int], ...]

_SPAWN: dict[PieceType, tuple[int, Cells]] = {
    # type: (box size, spawn-state cells)
    PieceType.I: (4, ((1, 0), (1, 1), (1, 2), (1, 3))),
    PieceType.O: (2, ((0, 0), (0, 1), (1, 0), (1, 1))),
    PieceType.T: (3, ((0, 1), (1, 0), (1, 1), (1, 2))),
    PieceType.S: (3, ((0, 1), (0, 2), (1, 0), (1, 1))),
    PieceType.Z: (3, ((0, 0), (0, 1), (1, 1), (1, 2))),
    PieceType.J: (3, ((0, 0), (1, 0), (1, 1), (1, 2))),
    PieceType.L: (3, ((0, 2), (1, 0), (1, 1), (1, 2))),
}


def _rotate_cw(cells: Cells, size: int) -> Cells:
    return tuple(sorted((c, size - 1 - r) for r, c in cells))


def _build_states(size: int, spawn: Cells) -> tuple[Cells, Cells, Cells, Cells]:
    s0 = tuple(sorted(spawn))
    s1 = _rotate_cw(s0, size)
    s2 = _rotate_cw(s1, size)
    s3 = _rotate_cw(s2, size)
    return (s0, s1, s2, s3)


@dataclass(frozen=True)
class PieceShape:
    type: PieceType
    size: int
    states: tuple[Cells, Cells, Cells, Cells]


SHAPES: dict[PieceType, PieceShape] = {
    t: PieceShape(t, size, _build_states(size, cells)) for t, (size, cells) in _SPAWN.items()
}


def _to_row_col(kicks: tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    """Convert SRS (x, y-up) offsets to (d_row, d_col)."""
    return tuple((-y, x) for x, y in kicks)


# Keys: (from_state, to_state). Values: offsets tried in order.
_JLSTZ_KICKS_XY = {
    (0, 1): ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)),
    (1, 0): ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2)),
    (1, 2): ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2)),
    (2, 1): ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)),
    (2, 3): ((0, 0), (1, 0), (1, 1), (0, -2), (1, -2)),
    (3, 2): ((0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)),
    (3, 0): ((0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)),
    (0, 3): ((0, 0), (1, 0), (1, 1), (0, -2), (1, -2)),
}

_I_KICKS_XY = {
    (0, 1): ((0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)),
    (1, 0): ((0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)),
    (1, 2): ((0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)),
    (2, 1): ((0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)),
    (2, 3): ((0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)),
    (3, 2): ((0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)),
    (3, 0): ((0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)),
    (0, 3): ((0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)),
}

JLSTZ_KICKS = {k: _to_row_col(v) for k, v in _JLSTZ_KICKS_XY.items()}
I_KICKS = {k: _to_row_col(v) for k, v in _I_KICKS_XY.items()}


def kicks_for(piece: PieceType, from_state: int, to_state: int) -> tuple[tuple[int, int], ...]:
    if piece is PieceType.O:
        return ((0, 0),)
    table = I_KICKS if piece is PieceType.I else JLSTZ_KICKS
    return table[(from_state, to_state)]


@dataclass(frozen=True)
class ActivePiece:
    """A piece on the board: type, rotation state, and box top-left (row, col)."""

    type: PieceType
    rotation: int
    row: int
    col: int

    @property
    def shape(self) -> PieceShape:
        return SHAPES[self.type]

    def cells(self) -> list[tuple[int, int]]:
        return [(self.row + r, self.col + c) for r, c in self.shape.states[self.rotation]]

    def moved(self, d_row: int = 0, d_col: int = 0) -> ActivePiece:
        return ActivePiece(self.type, self.rotation, self.row + d_row, self.col + d_col)

    def rotated(self, rotation: int, d_row: int = 0, d_col: int = 0) -> ActivePiece:
        return ActivePiece(self.type, rotation % 4, self.row + d_row, self.col + d_col)
