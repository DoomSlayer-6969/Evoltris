"""Main loop: fixed-timestep simulation, variable-rate rendering."""

from __future__ import annotations

import pygame

from evoltris.config import GameConfig
from evoltris.sim.world import World
from evoltris.ui.input import Command, InputHandler
from evoltris.ui.renderer import Renderer

_ALWAYS_KEYS = {pygame.K_ESCAPE, pygame.K_p, pygame.K_r, pygame.K_g, pygame.K_c}
"""Keys handled even while paused or after game over."""

MAX_FRAME_TIME = 0.25
"""Clamp long frames (e.g. window drag) so the simulation doesn't spiral."""


def run(config: GameConfig | None = None) -> None:
    config = config or GameConfig()
    pygame.init()
    pygame.display.set_caption("Evoltris")
    world = World(config)
    renderer = Renderer(world, config.render)
    screen = pygame.display.set_mode(renderer.size)
    controls = InputHandler(config.input)
    clock = pygame.time.Clock()
    accumulator = 0.0

    running = True
    while running:
        frame_dt = min(clock.tick(config.render.fps) / 1000.0, MAX_FRAME_TIME)

        for event in pygame.event.get():
            playing = not world.paused and not world.tetris.game_over
            if not playing and event.type == pygame.KEYDOWN and event.key not in _ALWAYS_KEYS:
                continue  # ignore gameplay keys while paused / game over
            cmd = controls.handle_event(event, world.tetris)
            if cmd is Command.QUIT:
                running = False
            elif cmd is Command.PAUSE:
                world.paused = not world.paused
                controls.reset()
            elif cmd is Command.RESTART:
                world = World(config)
                controls.reset()
                accumulator = 0.0
            elif cmd is Command.TOGGLE_LIFE:
                renderer.show_life = not renderer.show_life
            elif cmd is Command.TOGGLE_CML:
                renderer.show_cml = not renderer.show_cml

        if not world.paused and not world.tetris.game_over:
            controls.update(frame_dt, world.tetris)
            world.dispatch_lock_events()
            accumulator += frame_dt
            while accumulator >= config.sim_dt:
                world.step(config.sim_dt)
                accumulator -= config.sim_dt

        renderer.draw(screen, world)
        pygame.display.flip()

    pygame.quit()
