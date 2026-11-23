"""pygame rendering. Reads engine state; never mutates it."""

from __future__ import annotations

import numpy as np
import pygame

from evoltris.config import RenderConfig
from evoltris.coupling.board_life import BoardLifeCoupling
from evoltris.sim.world import World
from evoltris.tetris.pieces import GARBAGE, SHAPES, ActivePiece, PieceType
from evoltris.ui.input import CONTROLS_HELP

PIECE_COLOURS: dict[int, tuple[int, int, int]] = {
    PieceType.I: (0, 200, 220),
    PieceType.O: (230, 200, 0),
    PieceType.T: (160, 60, 200),
    PieceType.S: (60, 200, 80),
    PieceType.Z: (220, 60, 60),
    PieceType.J: (50, 90, 220),
    PieceType.L: (240, 140, 20),
    GARBAGE: (105, 108, 122),
}

BG = (14, 15, 20)
GRID_LINE = (32, 34, 44)
TEXT = (220, 222, 230)
MUTED = (130, 134, 150)
LIFE_COLOUR = (235, 235, 245)
DEATH_MARK = (14, 15, 20)

# CML heatmap ramp: value 0 → cool dark, 0.5 → teal, 1 → warm.
_RAMP_STOPS = np.array([0.0, 0.5, 1.0])
_RAMP_COLOURS = np.array([[16, 18, 40], [14, 62, 70], [110, 66, 26]], dtype=np.float64)


def cml_to_rgb(state: np.ndarray) -> np.ndarray:
    """Map CML values in [0,1] to an (H, W, 3) uint8 RGB array."""
    out = np.empty(state.shape + (3,), dtype=np.float64)
    for ch in range(3):
        out[..., ch] = np.interp(state, _RAMP_STOPS, _RAMP_COLOURS[:, ch])
    return out.astype(np.uint8)


class Renderer:
    def __init__(self, world: World, config: RenderConfig | None = None) -> None:
        self.config = config or RenderConfig()
        self.show_life = self.config.show_life
        self.show_cml = self.config.show_cml
        b = world.config.board
        self.cols = b.width
        self.rows = b.height
        self.hidden = b.hidden_rows
        cs = self.config.cell_size
        self.board_rect = pygame.Rect(0, 0, self.cols * cs, self.rows * cs)
        self.size = (self.board_rect.width + self.config.sidebar_width, self.board_rect.height)
        self.font = pygame.font.SysFont("monospace", 16)
        self.big_font = pygame.font.SysFont("monospace", 28, bold=True)

    # ---------------------------------------------------------------- helpers

    def _cell_rect(self, row: int, col: int) -> pygame.Rect:
        cs = self.config.cell_size
        return pygame.Rect(col * cs, (row - self.hidden) * cs, cs, cs)

    def _draw_block(self, surf: pygame.Surface, row: int, col: int, colour, alpha=255) -> None:
        if row < self.hidden:
            return
        rect = self._cell_rect(row, col).inflate(-2, -2)
        if alpha == 255:
            pygame.draw.rect(surf, colour, rect, border_radius=3)
        else:
            pygame.draw.rect(surf, colour, rect, width=2, border_radius=3)

    def _draw_piece(self, surf: pygame.Surface, piece: ActivePiece, ghost: bool = False) -> None:
        colour = PIECE_COLOURS[piece.type]
        for r, c in piece.cells():
            self._draw_block(surf, r, c, colour, alpha=90 if ghost else 255)

    # ----------------------------------------------------------------- layers

    def _draw_cml(self, surf: pygame.Surface, world: World) -> None:
        visible = world.cml.state[self.hidden :]
        rgb = cml_to_rgb(visible)  # (H, W, 3)
        small = pygame.surfarray.make_surface(rgb.transpose(1, 0, 2))
        surf.blit(pygame.transform.scale(small, self.board_rect.size), (0, 0))

    def _draw_grid(self, surf: pygame.Surface) -> None:
        cs = self.config.cell_size
        for c in range(self.cols + 1):
            pygame.draw.line(surf, GRID_LINE, (c * cs, 0), (c * cs, self.board_rect.height))
        for r in range(self.rows + 1):
            pygame.draw.line(surf, GRID_LINE, (0, r * cs), (self.board_rect.width, r * cs))

    def _draw_life(self, surf: pygame.Surface, world: World) -> None:
        cs = self.config.cell_size
        radius = max(2, cs // 6)
        rows, cols = np.nonzero(world.life.grid[self.hidden :])
        for r, c in zip(rows, cols):
            center = (int(c) * cs + cs // 2, int(r) * cs + cs // 2)
            pygame.draw.circle(surf, LIFE_COLOUR, center, radius)

    def _draw_life_preview(self, surf: pygame.Surface, world: World) -> None:
        """Board-life mode: mark what the next generation will do to the stack."""
        assert isinstance(world.coupling, BoardLifeCoupling)
        cs = self.config.cell_size
        board = world.tetris.board[self.hidden :]
        nxt = world.coupling.preview(world.tetris, settle=False)[self.hidden :]
        born = (board == 0) & (nxt != 0)
        dies = (board != 0) & (nxt == 0)
        for r, c in zip(*np.nonzero(born)):
            rect = self._cell_rect(int(r) + self.hidden, int(c)).inflate(-cs // 3, -cs // 3)
            pygame.draw.rect(surf, LIFE_COLOUR, rect, width=2, border_radius=2)
        radius = max(2, cs // 6)
        for r, c in zip(*np.nonzero(dies)):
            center = (int(c) * cs + cs // 2, int(r) * cs + cs // 2)
            pygame.draw.circle(surf, DEATH_MARK, center, radius)

    def _draw_board(self, surf: pygame.Surface, world: World) -> None:
        board = world.tetris.board
        rows, cols = np.nonzero(board)
        for r, c in zip(rows, cols):
            self._draw_block(surf, int(r), int(c), PIECE_COLOURS[int(board[r, c])])
        ghost = world.tetris.ghost()
        if ghost is not None:
            self._draw_piece(surf, ghost, ghost=True)
        if world.tetris.active is not None:
            self._draw_piece(surf, world.tetris.active)

    def _text(self, surf, text, pos, font=None, colour=TEXT) -> int:
        img = (font or self.font).render(text, True, colour)
        surf.blit(img, pos)
        return img.get_height()

    def _draw_mini_piece(self, surf, piece_type: PieceType, x: int, y: int, cs: int) -> None:
        shape = SHAPES[piece_type]
        for r, c in shape.states[0]:
            rect = pygame.Rect(x + c * cs, y + r * cs, cs - 1, cs - 1)
            pygame.draw.rect(surf, PIECE_COLOURS[piece_type], rect, border_radius=2)

    def _draw_sidebar(self, surf: pygame.Surface, world: World) -> None:
        x = self.board_rect.width + 16
        y = 14
        t = world.tetris
        y += self._text(surf, "EVOLTRIS", (x, y), self.big_font) + 10
        for line in (f"Score  {t.score}", f"Lines  {t.lines}", f"Level  {t.level}"):
            y += self._text(surf, line, (x, y)) + 2
        y += 10
        y += self._text(surf, "Next", (x, y), colour=MUTED) + 4
        for p in t.next_pieces:
            self._draw_mini_piece(surf, p, x, y, 16)
            y += 16 * 2 + 10
        y += 6
        life_state = "on" if self.show_life else "hidden"
        cml_state = "on" if self.show_cml else "hidden"
        if isinstance(world.coupling, BoardLifeCoupling):
            n = world.coupling.locks_until_generation
            life_stats = (
                f"Life gen {world.life.generation} ({life_state})",
                f"  evolves in {n} lock{'s' if n != 1 else ''}",
            )
        else:
            life_stats = (
                f"Life gen {world.life.generation} ({life_state})",
                f"  pop {world.life.population}",
            )
        stats = (
            *life_stats,
            f"CML step {world.cml.steps} ({cml_state})",
            f"  mean {world.cml.mean:.3f}",
            f"  r={world.config.cml.r} eps={world.config.cml.coupling}",
        )
        for line in stats:
            y += self._text(surf, line, (x, y), colour=MUTED) + 2
        y += 12
        for line in CONTROLS_HELP:
            y += self._text(surf, line, (x, y), colour=MUTED) + 1

    def _draw_banner(self, surf: pygame.Surface, text: str) -> None:
        overlay = pygame.Surface(self.board_rect.size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surf.blit(overlay, (0, 0))
        img = self.big_font.render(text, True, TEXT)
        surf.blit(img, img.get_rect(center=self.board_rect.center))

    # ------------------------------------------------------------------ frame

    def draw(self, surf: pygame.Surface, world: World) -> None:
        surf.fill(BG)
        if self.show_cml:
            self._draw_cml(surf, world)
        self._draw_grid(surf)
        board_life = isinstance(world.coupling, BoardLifeCoupling)
        if self.show_life and not board_life:
            self._draw_life(surf, world)
        self._draw_board(surf, world)
        if self.show_life and board_life and not world.tetris.game_over:
            self._draw_life_preview(surf, world)
        self._draw_sidebar(surf, world)
        if world.tetris.game_over:
            self._draw_banner(surf, "GAME OVER  (R)")
        elif world.paused:
            self._draw_banner(surf, "PAUSED")
