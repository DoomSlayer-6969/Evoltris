"""Headless renderer tests (SDL dummy video driver): smoke runs and pixel checks."""

import dataclasses
import itertools
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame
import pytest

from evoltris.config import CMLConfig, CouplingConfig, GameConfig, TetrisConfig
from evoltris.sim.world import World
from evoltris.tetris.pieces import PieceType
from evoltris.ui.renderer import BG, DEATH_MARK, FERTILE, LIFE_COLOUR, Renderer, cml_to_rgb


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    yield
    pygame.quit()


def make(coupling=None):
    cfg = GameConfig(tetris=TetrisConfig(seed=0), cml=CMLConfig(seed=0))
    if coupling is not None:
        cfg = dataclasses.replace(cfg, coupling=coupling)
    w = World(cfg)
    r = Renderer(w, cfg.render)
    return w, r, pygame.Surface(r.size)


def centre(r, row, col):
    """Pixel at the centre of board cell (row, col), in board coordinates."""
    return r._cell_rect(row, col).center


def pixel(surf, xy):
    return tuple(surf.get_at(xy))[:3]


@pytest.mark.parametrize(
    "mode,show_life,show_cml",
    list(itertools.product(["board_life", "none"], [True, False], [True, False])),
)
def test_draw_runs_in_every_mode(mode, show_life, show_cml):
    w, r, surf = make(CouplingConfig(mode=mode))
    r.show_life, r.show_cml = show_life, show_cml
    r.draw(surf, w)
    w.paused = True
    r.draw(surf, w)
    w.tetris.game_over = True
    r.draw(surf, w)


def test_cml_overlay_shows_frozen_fertility_mask():
    w, r, surf = make()
    row = r.hidden + 5  # empty cell, well above the ghost piece
    for col, fertile in ((3, True), (4, False)):
        w.coupling.fertile[row, col] = fertile
    r.draw(surf, w)
    assert pixel(surf, centre(r, row, 3)) == FERTILE
    assert pixel(surf, centre(r, row, 4)) == BG


def test_cml_overlay_without_coupling_shows_live_heatmap():
    w, r, surf = make(CouplingConfig(mode="none"))
    r.show_life = False
    row, col = r.hidden + 5, 3
    w.cml.state[row, col] = 1.0
    r.draw(surf, w)
    expected = tuple(int(v) for v in cml_to_rgb(np.array([[1.0]]))[0, 0])
    assert pixel(surf, centre(r, row, col)) == expected


def test_life_preview_marks_births_and_deaths():
    w, r, surf = make()
    w.coupling.fertile = None  # every cell may change
    r.show_cml = False
    w.tetris.board[10, 3:6] = PieceType.I  # blinker: (10,3) dies, (9,4) is born
    r.draw(surf, w)
    cs = r.config.cell_size
    birth = r._cell_rect(9, 4).inflate(-cs // 3, -cs // 3)
    assert pixel(surf, (birth.left, birth.centery)) == LIFE_COLOUR
    assert pixel(surf, centre(r, 10, 3)) == DEATH_MARK

