import numpy as np
import pytest

from evoltris.cml.engine import CMLEngine
from evoltris.config import BoardConfig, CMLConfig, CouplingConfig, LifeConfig, TetrisConfig
from evoltris.coupling.board_life import (
    BoardLifeCoupling,
    board_life_step,
    settle_clusters,
    settle_columns,
    surface_mask,
)
from evoltris.life.engine import LifeEngine
from evoltris.tetris.engine import TetrisEngine
from evoltris.tetris.pieces import GARBAGE, ActivePiece, PieceType

H, W, HID = 22, 10, 2


def empty():
    return np.zeros((H, W), dtype=np.uint8)


# ------------------------------------------------------------ board_life_step


def test_still_life_block_survives_with_its_colours():
    b = empty()
    b[10:12, 4:6] = [[PieceType.T, PieceType.S], [PieceType.Z, PieceType.L]]
    np.testing.assert_array_equal(board_life_step(b, HID), b)


def test_blinker_oscillates_survivor_keeps_colour_births_are_garbage():
    b = empty()
    b[10, 3:6] = PieceType.I
    out = board_life_step(b, HID)
    expected = empty()
    expected[9:12, 4] = GARBAGE
    expected[10, 4] = PieceType.I  # centre survives with its original colour
    np.testing.assert_array_equal(out, expected)


def test_solid_slab_dies_inside_and_is_reborn_on_top():
    """Documents the harsh effect on dense stacks under the fixed boundary."""
    b = empty()
    b[18:22, :] = PieceType.O
    out = board_life_step(b, HID)
    alive = out != 0
    assert alive[17, 1:9].all() and (out[17, 1:9] == GARBAGE).all()
    assert not alive[19:21, 1:9].any()  # interior is hollowed out


def test_input_board_is_not_modified():
    b = empty()
    b[10, 3:6] = PieceType.I
    before = b.copy()
    board_life_step(b, HID)
    np.testing.assert_array_equal(b, before)


def test_hidden_rows_are_untouched_and_not_neighbours():
    b = empty()
    b[1, 3:6] = PieceType.I  # would be a blinker if it were visible
    b[0, 0] = PieceType.O
    out = board_life_step(b, HID)
    np.testing.assert_array_equal(out[:HID], b[:HID])
    # (2, 4) is directly below three hidden cells: no birth across the boundary.
    assert not out[HID:].any()


def test_protected_cells_receive_no_birth():
    b = empty()
    b[10, 3:6] = PieceType.I
    out = board_life_step(b, HID, protected=[(9, 4)])
    assert out[9, 4] == 0
    assert out[11, 4] == GARBAGE


def test_periodic_boundary_wraps():
    b = empty()
    b[10, [9, 0, 1]] = PieceType.J  # blinker split across the side wall
    out = board_life_step(b, HID, boundary="periodic")
    assert out[9, 0] == GARBAGE and out[11, 0] == GARBAGE and out[10, 0] == PieceType.J
    assert out[10, 9] == 0 and out[10, 1] == 0


# --------------------------------------------------------------- engine hooks


@pytest.fixture
def eng():
    return TetrisEngine(BoardConfig(), TetrisConfig(seed=0))


def test_replace_board_clears_and_scores_full_rows(eng):
    b = empty()
    b[21, :] = GARBAGE
    b[20, 0] = PieceType.I
    cleared = eng.replace_board(b)
    assert cleared == (21,)
    assert eng.lines == 1 and eng.score == 100
    assert eng.board[21, 0] == PieceType.I and eng.board.sum() == PieceType.I


def test_replace_board_blocks_out_when_active_piece_is_covered(eng):
    b = empty()
    r, c = next(iter(eng.active.cells()))
    b[r, c] = GARBAGE
    eng.replace_board(b)
    assert eng.game_over and eng.active is None


def test_replace_board_rejects_wrong_shape(eng):
    with pytest.raises(ValueError):
        eng.replace_board(np.zeros((3, 3), dtype=np.uint8))


def test_locks_per_generation_must_be_positive():
    with pytest.raises(ValueError):
        CouplingConfig(locks_per_generation=0)


def test_surface_depth_must_be_positive_or_none():
    with pytest.raises(ValueError):
        CouplingConfig(surface_depth=0)
    assert CouplingConfig(surface_depth=None).surface_depth is None


def test_default_coupling_is_the_tuned_balance():
    c = CouplingConfig()
    assert (c.mode, c.locks_per_generation, c.surface_depth, c.settle) == (
        "board_life",
        8,
        1,
        "clusters",
    )


# ---------------------------------------------------------- surface / settling


def test_surface_mask_follows_each_column_top():
    alive = np.zeros((6, 3), dtype=bool)
    alive[2:, 0] = True  # column 0 top at row 2
    alive[5, 1] = True  # column 1 top at row 5; column 2 empty
    m = surface_mask(alive, 2)
    assert m[:, 0].tolist() == [True, True, True, True, False, False]
    assert m[:, 1].all() and m[:, 2].all()


def test_surface_depth_freezes_deep_blocks_but_they_still_count():
    b = empty()
    b[17:22, 2:7] = PieceType.O  # solid 5x5 slab
    whole = board_life_step(b, HID)
    shallow = board_life_step(b, HID, surface_depth=1)
    assert (whole[18:21, 3:6] == 0).all()  # whole-board rule hollows the interior
    np.testing.assert_array_equal(shallow[18:, 2:7], b[18:, 2:7])  # depth 1: slab intact
    # Empty neighbouring columns are open to the sky, so births on the exposed
    # sides of the slab still happen.
    assert (shallow[18:21, [1, 7]] == GARBAGE).all()
    # The top row of the slab is in the surface; overcrowded cells there die.
    assert (shallow[17, 3:6] == 0).all()
    assert (shallow[16, 3:6] == GARBAGE).all()


def test_settle_columns_closes_every_gap_and_keeps_order():
    g = np.zeros((5, 2), dtype=np.uint8)
    g[0, 0], g[2, 0], g[4, 1] = 1, 2, 3
    out = settle_columns(g)
    assert out[:, 0].tolist() == [0, 0, 0, 1, 2]
    assert out[:, 1].tolist() == [0, 0, 0, 0, 3]


def test_settle_clusters_drops_groups_rigidly():
    g = np.zeros((6, 4), dtype=np.uint8)
    g[5, :] = 1  # floor row
    g[1, 0:3] = 2  # floating bar, one cell overhangs a deeper gap below
    g[3, 3] = 3  # floating single block
    g[4, 1] = 0
    out = settle_clusters(g)
    assert out[4, 0:3].tolist() == [2, 2, 2]  # bar lands on the floor as a unit
    assert out[4, 3] == 3
    assert out[:4].sum() == 0


def test_settle_clusters_keeps_supported_overhangs():
    g = np.zeros((4, 3), dtype=np.uint8)
    g[3, 0] = 1
    g[2, 0:3] = 2  # T-shaped group resting on (3, 0), overhanging a hole at (3, 1..2)
    out = settle_clusters(g)
    np.testing.assert_array_equal(out, g)


def test_settle_clusters_merges_landed_groups():
    g = np.zeros((5, 1), dtype=np.uint8)
    g[0, 0], g[2, 0] = 1, 2
    out = settle_clusters(g)
    assert out[:, 0].tolist() == [0, 0, 0, 1, 2]


def test_settling_only_moves_visible_rows():
    b = empty()
    b[0, 0] = PieceType.O  # hidden block must stay put
    b[5, 5] = PieceType.T  # isolated visible block: dies, nothing left to settle
    b[10, 3:6] = PieceType.I
    out = board_life_step(b, HID, settle="columns")
    assert out[0, 0] == PieceType.O
    assert out[HID:].sum() and out[-3:, 4].tolist() == [GARBAGE, PieceType.I, GARBAGE]


# ------------------------------------------------------------------- coupling


def make(n=3, boundary="fixed", surface_depth=None, settle="none"):
    """Defaults give the raw rule (whole board, no settling) for exact assertions."""
    tetris = TetrisEngine(BoardConfig(), TetrisConfig(seed=0))
    life = LifeEngine((H, W), LifeConfig())
    cfg = CouplingConfig(
        mode="board_life",
        locks_per_generation=n,
        boundary=boundary,
        surface_depth=surface_depth,
        settle=settle,
    )
    coupling = BoardLifeCoupling(cfg, HID)
    return tetris, life, coupling


def test_generation_applied_every_n_locks():
    tetris, life, cp = make(n=3)
    seen = []
    for _ in range(7):
        event = tetris.hard_drop()
        before = tetris.board.copy()
        cp.on_piece_locked(event, tetris, life, None)
        seen.append((life.generation, not np.array_equal(before, tetris.board)))
    assert [g for g, _ in seen] == [0, 0, 1, 1, 1, 2, 2]
    assert cp.locks_until_generation == 2


def test_evolve_matches_preview_and_mirrors_into_life():
    tetris, life, cp = make()
    tetris.board[10, 3:6] = PieceType.I
    expected = cp.preview(tetris)
    cp.evolve(tetris, life)
    np.testing.assert_array_equal(tetris.board, expected)
    np.testing.assert_array_equal(life.grid, (expected != 0).astype(np.uint8))
    assert life.generation == 1


def test_evolve_never_births_into_active_piece():
    tetris, life, cp = make()
    tetris.active = ActivePiece(PieceType.O, 0, 9, 4)  # occupies rows 9-10, cols 5-6
    cells = set(tetris.active.cells())
    # Surround each active cell with exactly three blocks so all would be born.
    tetris.board[8, 4:8] = PieceType.T
    tetris.board[11, 4:8] = PieceType.T
    assert any(cp.preview(tetris)[r, c] == 0 for r, c in cells)
    cp.evolve(tetris, life)
    assert not tetris.game_over
    assert all(tetris.board[r, c] == 0 for r, c in cells)


def test_generation_born_line_is_cleared_and_scored():
    tetris, life, cp = make(boundary="periodic")
    row = 15
    tetris.board[row, :] = PieceType.I
    tetris.board[row, 4] = 0
    tetris.board[row - 1, 4] = PieceType.T
    # The gap has exactly 3 neighbours and is born, completing the row. Every
    # cell of the row above also has 3 (or, at col 4, 2 with itself alive), so
    # it fills completely too: two lines are cleared and scored as a double.
    cleared = cp.evolve(tetris, life)
    assert cleared == (row - 1, row)
    assert tetris.lines == 2 and tetris.score == 300


def test_no_generation_after_game_over():
    tetris, life, cp = make(n=1)
    tetris.board[10, 3:6] = PieceType.I
    tetris.game_over = True
    before = tetris.board.copy()
    cp.on_piece_locked(None, tetris, life, None)
    np.testing.assert_array_equal(tetris.board, before)
    assert life.generation == 0 and cp.locks_since_generation == 0


def test_preview_without_settle_shows_raw_life_changes():
    tetris, life, cp = make(settle="clusters")
    tetris.board[10, 3:6] = PieceType.I
    raw = cp.preview(tetris, settle=False)
    settled = cp.preview(tetris)
    assert raw[9, 4] == GARBAGE and raw[11, 4] == GARBAGE
    assert settled[-3:, 4].tolist() == [GARBAGE, PieceType.I, GARBAGE]
    cp.evolve(tetris, life)
    np.testing.assert_array_equal(tetris.board, settled)


# --------------------------------------------------------- CML fertility mask


def blinker():
    b = empty()
    b[10, 3:6] = PieceType.I  # horizontal blinker: ends die, (9,4) and (11,4) are born
    return b


def test_fertility_mask_freezes_infertile_cells():
    b = blinker()
    fertile = np.ones((H, W), dtype=bool)
    fertile[10, 3] = False  # this end survives instead of dying
    fertile[9, 4] = False  # no birth here
    out = board_life_step(b, HID, fertile=fertile)
    assert out[10, 3] == PieceType.I and out[10, 5] == 0
    assert out[9, 4] == 0 and out[11, 4] == GARBAGE


def test_frozen_cells_still_count_as_neighbours():
    b = blinker()
    fertile = np.zeros((H, W), dtype=bool)
    fertile[11, 4] = True  # only the birth below the centre may happen
    out = board_life_step(b, HID, fertile=fertile)
    expected = b.copy()
    expected[11, 4] = GARBAGE
    np.testing.assert_array_equal(out, expected)


def test_all_fertile_matches_no_mask():
    b = blinker()
    np.testing.assert_array_equal(
        board_life_step(b, HID, fertile=np.ones((H, W), dtype=bool)), board_life_step(b, HID)
    )


def test_fertility_threshold_must_be_in_unit_interval():
    for bad in (-0.1, 1.1):
        with pytest.raises(ValueError):
            CouplingConfig(fertility_threshold=bad)
    assert CouplingConfig(fertility_threshold=None).fertility_threshold is None


def make_cml(enabled=True):
    cml = CMLEngine((H, W), CMLConfig(seed=0, enabled=enabled))
    cml.randomize()
    return cml


def test_mask_is_snapshotted_at_start_and_fixed_until_next_generation():
    tetris, life, cp = make(n=2)
    cml = make_cml()
    cp.on_start(tetris, life, cml)
    np.testing.assert_array_equal(cp.fertile, cml.state > 0.5)
    first = cp.fertile.copy()
    cml.step()
    assert not np.array_equal(cml.state > 0.5, first)
    cp.on_piece_locked(tetris.hard_drop(), tetris, life, cml)
    np.testing.assert_array_equal(cp.fertile, first)  # not yet re-snapshotted
    cml.step()
    cp.on_piece_locked(tetris.hard_drop(), tetris, life, cml)  # generation happens
    assert life.generation == 1
    np.testing.assert_array_equal(cp.fertile, cml.state > 0.5)


def test_preview_uses_the_fertility_mask():
    tetris, life, cp = make()
    tetris.board[:] = blinker()
    cml = make_cml()
    cml.set_state(np.zeros((H, W)))  # nothing is fertile
    cp.on_start(tetris, life, cml)
    np.testing.assert_array_equal(cp.preview(tetris), tetris.board)


def test_no_mask_when_threshold_is_none_or_cml_disabled():
    tetris, life, _ = make()
    cp = BoardLifeCoupling(CouplingConfig(fertility_threshold=None), HID)
    cp.on_start(tetris, life, make_cml())
    assert cp.fertile is None
    cp = BoardLifeCoupling(CouplingConfig(), HID)
    cp.on_start(tetris, life, make_cml(enabled=False))
    assert cp.fertile is None
