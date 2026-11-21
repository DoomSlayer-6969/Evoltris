"""Keyboard handling with DAS/ARR auto-repeat, translated into engine actions."""

from __future__ import annotations

from enum import Enum, auto

import pygame

from evoltris.config import InputConfig
from evoltris.tetris.engine import TetrisEngine


class Command(Enum):
    QUIT = auto()
    PAUSE = auto()
    RESTART = auto()
    TOGGLE_LIFE = auto()
    TOGGLE_CML = auto()


KEY_COMMANDS = {
    pygame.K_ESCAPE: Command.QUIT,
    pygame.K_p: Command.PAUSE,
    pygame.K_r: Command.RESTART,
    pygame.K_g: Command.TOGGLE_LIFE,
    pygame.K_c: Command.TOGGLE_CML,
}

CONTROLS_HELP = (
    "Left/Right  move",
    "Down        soft drop",
    "Up / X      rotate CW",
    "Z           rotate CCW",
    "Space       hard drop",
    "G / C       toggle Life / CML",
    "P  pause   R  restart",
    "Esc         quit",
)


class _Repeater:
    """Tracks one held key: fires on press, then after DAS, then every ARR."""

    def __init__(self, delay: float, rate: float) -> None:
        self.delay = delay
        self.rate = rate
        self.held = False
        self.timer = 0.0
        self.repeating = False

    def press(self) -> None:
        self.held, self.timer, self.repeating = True, 0.0, False

    def release(self) -> None:
        self.held = False

    def tick(self, dt: float) -> int:
        """Return how many repeat fires happened during ``dt``."""
        if not self.held:
            return 0
        self.timer += dt
        fires = 0
        if not self.repeating:
            if self.timer < self.delay:
                return 0
            self.repeating = True
            self.timer -= self.delay
            fires += 1
        while self.timer >= self.rate:
            self.timer -= self.rate
            fires += 1
        return fires


class InputHandler:
    def __init__(self, config: InputConfig | None = None) -> None:
        cfg = config or InputConfig()
        self.left = _Repeater(cfg.das, cfg.arr)
        self.right = _Repeater(cfg.das, cfg.arr)
        self.down = _Repeater(0.0, cfg.soft_drop_interval)

    def reset(self) -> None:
        for r in (self.left, self.right, self.down):
            r.release()

    def handle_event(self, event: pygame.event.Event, tetris: TetrisEngine) -> Command | None:
        if event.type == pygame.QUIT:
            return Command.QUIT
        if event.type == pygame.KEYDOWN:
            if event.key in KEY_COMMANDS:
                return KEY_COMMANDS[event.key]
            if event.key == pygame.K_LEFT:
                self.right.release()
                self.left.press()
                tetris.move(-1)
            elif event.key == pygame.K_RIGHT:
                self.left.release()
                self.right.press()
                tetris.move(1)
            elif event.key == pygame.K_DOWN:
                self.down.press()
                tetris.soft_drop_step()
            elif event.key in (pygame.K_UP, pygame.K_x):
                tetris.rotate(1)
            elif event.key in (pygame.K_z, pygame.K_LCTRL, pygame.K_RCTRL):
                tetris.rotate(-1)
            elif event.key == pygame.K_SPACE:
                tetris.hard_drop()
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_LEFT:
                self.left.release()
            elif event.key == pygame.K_RIGHT:
                self.right.release()
            elif event.key == pygame.K_DOWN:
                self.down.release()
        return None

    def update(self, dt: float, tetris: TetrisEngine) -> None:
        for _ in range(self.left.tick(dt)):
            tetris.move(-1)
        for _ in range(self.right.tick(dt)):
            tetris.move(1)
        for _ in range(self.down.tick(dt)):
            tetris.soft_drop_step()
