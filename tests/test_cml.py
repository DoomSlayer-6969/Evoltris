import numpy as np
import pytest

from evoltris.cml.engine import CMLEngine, cml_step
from evoltris.cml.maps import LogisticMap
from evoltris.config import CMLConfig


def reference_step(x, r, eps, boundary):
    """Explicit-loop implementation of the Kaneko CML for cross-checking."""
    h, w = x.shape
    f = r * x * (1 - x)
    out = np.empty_like(x)
    for i in range(h):
        for j in range(w):
            s = 0.0
            for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ni, nj = i + di, j + dj
                if 0 <= ni < h and 0 <= nj < w:
                    s += f[ni, nj]
                elif boundary == "periodic":
                    s += f[ni % h, nj % w]
                elif boundary == "reflective":
                    s += f[i, j]
                # fixed: contributes 0
            out[i, j] = (1 - eps) * f[i, j] + eps / 4 * s
    return out


def test_logistic_map_values():
    m = LogisticMap(4.0)
    np.testing.assert_allclose(m(np.array([0.0, 0.25, 0.5, 1.0])), [0.0, 0.75, 1.0, 0.0])


def test_logistic_map_rejects_out_of_range_r():
    with pytest.raises(ValueError):
        LogisticMap(4.5)


def test_config_validates_parameters():
    with pytest.raises(ValueError):
        CMLConfig(r=-0.1)
    with pytest.raises(ValueError):
        CMLConfig(coupling=1.5)


def test_hand_computed_centre_cell():
    x = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]])
    r, eps = 4.0, 0.4
    out = cml_step(x, LogisticMap(r), eps, "fixed")
    f = lambda v: r * v * (1 - v)  # noqa: E731
    expected = (1 - eps) * f(0.5) + eps / 4 * (f(0.2) + f(0.8) + f(0.4) + f(0.6))
    assert out[1, 1] == pytest.approx(expected)
    # = 0.6 * 1.0 + 0.1 * (0.64 + 0.64 + 0.96 + 0.96) = 0.92
    assert out[1, 1] == pytest.approx(0.92)


@pytest.mark.parametrize("boundary", ["fixed", "periodic", "reflective"])
def test_matches_reference_implementation(boundary):
    x = np.random.default_rng(3).random((6, 5))
    out = cml_step(x, LogisticMap(3.7), 0.35, boundary)
    np.testing.assert_allclose(out, reference_step(x, 3.7, 0.35, boundary))


def test_zero_coupling_is_independent_logistic_maps():
    x = np.random.default_rng(1).random((5, 5))
    out = cml_step(x, LogisticMap(3.9), 0.0, "periodic")
    np.testing.assert_allclose(out, 3.9 * x * (1 - x))


@pytest.mark.parametrize("boundary", ["periodic", "reflective"])
def test_uniform_state_stays_uniform(boundary):
    x = np.full((6, 6), 0.3)
    out = cml_step(x, LogisticMap(3.9), 0.3, boundary)
    np.testing.assert_allclose(out, np.full((6, 6), 3.9 * 0.3 * 0.7))


@pytest.mark.parametrize("boundary", ["periodic", "reflective"])
def test_coupling_conserves_total_of_local_map(boundary):
    # Diffusive coupling only redistributes f-values: sum(x') == sum(f(x)).
    x = np.random.default_rng(5).random((7, 9))
    m = LogisticMap(3.8)
    out = cml_step(x, m, 0.45, boundary)
    assert out.sum() == pytest.approx(m(x).sum())


def test_transpose_symmetry():
    x = np.random.default_rng(2).random((6, 6))
    m = LogisticMap(3.6)
    np.testing.assert_allclose(cml_step(x.T, m, 0.3, "reflective"), cml_step(x, m, 0.3, "reflective").T)


@pytest.mark.parametrize("boundary", ["fixed", "periodic", "reflective"])
def test_state_stays_in_unit_interval(boundary):
    eng = CMLEngine((22, 10), CMLConfig(r=4.0, coupling=0.5, boundary=boundary, seed=9))
    eng.randomize()
    for _ in range(500):
        eng.step()
        assert eng.state.min() >= 0.0 and eng.state.max() <= 1.0
    assert eng.steps == 500


def test_set_state_rejects_values_outside_unit_interval():
    eng = CMLEngine((3, 3))
    with pytest.raises(ValueError):
        eng.set_state(np.full((3, 3), 1.2))
