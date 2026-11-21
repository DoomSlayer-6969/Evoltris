import numpy as np
import pytest

from evoltris.config import BoardConfig, TetrisConfig
from evoltris.tetris.engine import TetrisEngine
from evoltris.tetris.pieces import SHAPES, ActivePiece, PieceType
from evoltris.tetris.randomizer import BagRandomizer


@pytest.fixture
def eng():
    return TetrisEngine(BoardConfig(), TetrisConfig(seed=0))


def bottom(eng):
    return eng.board.shape[0] - 1


def test_every_shape_has_four_states_of_four_cells_and_cycles():
    for shape in SHAPES.values():
        assert len(shape.states) == 4
        for s in shape.states:
            assert len(s) == 4
            assert all(0 <= r < shape.size and 0 <= c < shape.size for r, c in s)


def test_srs_t_right_state():
    assert set(SHAPES[PieceType.T].states[1]) == {(0, 1), (1, 1), (2, 1), (1, 2)}


def test_spawn_is_centred_in_hidden_rows(eng):
    eng.spawn(PieceType.T)
    assert eng.active.cells() == [(0, 4), (1, 3), (1, 4), (1, 5)]
    eng.spawn(PieceType.I)
    assert sorted(c for _, c in eng.active.cells()) == [3, 4, 5, 6]


def test_wall_collision(eng):
    eng.spawn(PieceType.T)
    while eng.move(-1):
        pass
    assert min(c for _, c in eng.active.cells()) == 0
    while eng.move(1):
        pass
    assert max(c for _, c in eng.active.cells()) == 9


def test_stack_collision(eng):
    eng.board[bottom(eng), :] = 1
    eng.board[bottom(eng), 0] = 0
    eng.spawn(PieceType.O)
    eng.hard_drop()
    # O settles on top of the full-ish bottom row, not through it.
    assert eng.board[bottom(eng) - 1, 4] == PieceType.O


def test_hard_drop_to_floor_scores_per_row(eng):
    eng.spawn(PieceType.I)
    start_row = eng.active.cells()[0][0]
    event = eng.hard_drop()
    assert all(r == bottom(eng) for r, _ in event.cells)
    assert eng.score == 2 * (bottom(eng) - start_row)


@pytest.mark.parametrize("n,points", [(1, 100), (2, 300), (3, 500), (4, 800)])
def test_line_clear_scoring(eng, n, points):
    b = bottom(eng)
    eng.board[b - n + 1 : b + 1, :9] = PieceType.J
    eng.active = ActivePiece(PieceType.I, 1, 0, 7)  # vertical I in column 9
    drop_rows = b - 3 - 0
    event = eng.hard_drop()
    assert len(event.cleared_rows) == n
    assert eng.lines == n
    assert eng.score == points + 2 * drop_rows
    # Everything that remains is the part of the I that stuck out above the cleared rows.
    assert eng.board.sum() == (4 - n) * PieceType.I


def test_rows_above_cleared_line_shift_down(eng):
    b = bottom(eng)
    eng.board[b, :] = PieceType.S
    eng.board[b - 1, 0] = PieceType.Z
    assert eng.clear_full_rows() == (b,)
    assert eng.board[b, 0] == PieceType.Z
    assert eng.board[:b].sum() == 0


def test_srs_wall_kick_off_left_wall(eng):
    eng.active = ActivePiece(PieceType.T, 1, 5, -1)  # pointing right, flush with left wall
    assert eng.fits(eng.active)
    assert eng.rotate(1)  # 1 -> 2 needs the (+1, 0) kick
    assert eng.active.rotation == 2
    assert min(c for _, c in eng.active.cells()) == 0


def test_rotation_fails_when_all_kicks_blocked(eng):
    eng.board[:, :] = 1
    piece = ActivePiece(PieceType.T, 0, 10, 3)
    for r, c in piece.cells():
        eng.board[r, c] = 0
    eng.active = piece
    assert not eng.rotate(1)
    assert eng.active == piece


def test_o_rotation_does_not_move(eng):
    eng.spawn(PieceType.O)
    before = sorted(eng.active.cells())
    eng.rotate(1)
    assert sorted(eng.active.cells()) == before


def test_four_rotations_return_to_start(eng):
    eng.active = ActivePiece(PieceType.L, 0, 8, 4)
    for _ in range(4):
        assert eng.rotate(1)
    assert eng.active.rotation == 0
    assert sorted(eng.active.cells()) == sorted(ActivePiece(PieceType.L, 0, 8, 4).cells())


def test_gravity_moves_one_row_per_interval(eng):
    row = eng.active.row
    eng.update(eng.gravity_interval * 0.99)
    assert eng.active.row == row
    eng.update(eng.gravity_interval * 0.02)
    assert eng.active.row == row + 1


def test_lock_delay(eng):
    eng.spawn(PieceType.O)
    eng.active = eng.ghost()
    eng.update(eng.config.lock_delay * 0.5)
    assert not eng.drain_events()
    eng.update(eng.config.lock_delay * 0.6)
    events = eng.drain_events()
    assert len(events) == 1 and events[0].piece is PieceType.O


def test_soft_drop_scores(eng):
    eng.soft_drop_step()
    assert eng.score == 1


def test_game_over_when_spawn_blocked(eng):
    eng.board[0:2, 3:7] = 1
    assert not eng.spawn(PieceType.T)
    assert eng.game_over
    assert not eng.move(1)


def test_level_and_gravity_progression(eng):
    g0 = eng.gravity_interval
    eng.lines = 10
    assert eng.level == 1
    assert eng.gravity_interval == pytest.approx(g0 * eng.config.gravity_decay)


def test_seven_bag_contains_each_piece_once_per_bag():
    bag = BagRandomizer(seed=42)
    for _ in range(5):
        assert sorted(bag.next() for _ in range(7)) == sorted(PieceType)


def test_peek_matches_next():
    bag = BagRandomizer(seed=1)
    preview = bag.peek(10)
    assert [bag.next() for _ in range(10)] == preview


def test_board_values_are_piece_types(eng):
    eng.spawn(PieceType.Z)
    eng.hard_drop()
    assert set(np.unique(eng.board)) == {0, int(PieceType.Z)}
