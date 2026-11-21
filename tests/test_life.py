import numpy as np
import pytest

from evoltris.config import LifeConfig
from evoltris.life.engine import LifeEngine, life_step


def grid_with(cells, shape=(8, 8)):
    g = np.zeros(shape, dtype=np.uint8)
    for r, c in cells:
        g[r, c] = 1
    return g


def test_output_is_binary_and_input_untouched():
    g = np.random.default_rng(0).integers(0, 2, (10, 10), dtype=np.uint8)
    before = g.copy()
    out = life_step(g)
    assert set(np.unique(out)) <= {0, 1}
    assert out.dtype == np.uint8
    np.testing.assert_array_equal(g, before)


@pytest.mark.parametrize("n_neighbours", [0, 1])
def test_rule1_underpopulation(n_neighbours):
    cells = [(3, 3)] + [(2, 2), (2, 4)][:n_neighbours]
    assert life_step(grid_with(cells))[3, 3] == 0


@pytest.mark.parametrize("n_neighbours", [2, 3])
def test_rule2_survival(n_neighbours):
    nbrs = [(2, 2), (2, 4), (4, 3)][:n_neighbours]
    assert life_step(grid_with([(3, 3)] + nbrs))[3, 3] == 1


@pytest.mark.parametrize("n_neighbours", [4, 5, 8])
def test_rule3_overpopulation(n_neighbours):
    ring = [(2, 2), (2, 3), (2, 4), (3, 2), (3, 4), (4, 2), (4, 3), (4, 4)]
    assert life_step(grid_with([(3, 3)] + ring[:n_neighbours]))[3, 3] == 0


@pytest.mark.parametrize("n_neighbours,expected", [(2, 0), (3, 1), (4, 0)])
def test_rule4_reproduction_only_with_exactly_three(n_neighbours, expected):
    ring = [(2, 2), (2, 4), (4, 2), (4, 4)]
    assert life_step(grid_with(ring[:n_neighbours]))[3, 3] == expected


@pytest.mark.parametrize(
    "cells",
    [
        [(2, 2), (2, 3), (3, 2), (3, 3)],  # block
        [(2, 3), (2, 4), (3, 2), (3, 5), (4, 3), (4, 4)],  # beehive
    ],
)
def test_still_lifes(cells):
    g = grid_with(cells)
    np.testing.assert_array_equal(life_step(g), g)


def test_blinker_period_two():
    g = grid_with([(3, 2), (3, 3), (3, 4)])
    g1 = life_step(g)
    np.testing.assert_array_equal(g1, grid_with([(2, 3), (3, 3), (4, 3)]))
    np.testing.assert_array_equal(life_step(g1), g)


def test_glider_translates_diagonally_after_four_generations():
    glider = [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)]
    g = grid_with(glider, (12, 12))
    for _ in range(4):
        g = life_step(g)
    np.testing.assert_array_equal(g, grid_with([(r + 1, c + 1) for r, c in glider], (12, 12)))


def test_fixed_boundary_treats_outside_as_dead():
    # Blinker against the top edge: in fixed mode the cells above don't exist.
    g = grid_with([(0, 2), (0, 3), (0, 4)])
    out = life_step(g, "fixed")
    np.testing.assert_array_equal(out, grid_with([(0, 3), (1, 3)]))


def test_periodic_boundary_wraps():
    g = grid_with([(0, 2), (0, 3), (0, 4)])
    out = life_step(g, "periodic")
    np.testing.assert_array_equal(out, grid_with([(7, 3), (0, 3), (1, 3)]))


def test_engine_tracks_generation_and_population():
    eng = LifeEngine((8, 8), LifeConfig(seed=1))
    eng.set_grid(grid_with([(3, 2), (3, 3), (3, 4)]))
    eng.step()
    assert eng.generation == 1
    assert eng.population == 3


def test_randomize_is_seeded():
    a, b = LifeEngine((10, 10), LifeConfig(seed=7)), LifeEngine((10, 10), LifeConfig(seed=7))
    a.randomize()
    b.randomize()
    np.testing.assert_array_equal(a.grid, b.grid)
