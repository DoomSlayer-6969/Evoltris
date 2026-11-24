# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Evoltris combines Tetris with Conway's Game of Life and a Coupled Map Lattice (CML). See `README.md` for the controls, the full math, and the balance tables behind the default settings.

## Commands

The project uses `uv` and Python 3.14. No linter or formatter is configured.

```sh
uv run evoltris                                     # play (pygame window)
uv run pytest                                       # all tests (headless, <1s)
uv run pytest tests/test_coupling.py                # one file
uv run pytest tests/test_coupling.py::test_name     # one test
uv run pytest -k settle                             # by keyword
uv run python scripts/balance_sweep.py --games 24   # headless bot balance sweep (~1 min, parallel)
uv run python scripts/fit_difficulty.py --games 24  # refit the LPP's linear models (~3 min)
```

## Architecture

**The engines never reference each other.** `tetris/`, `life/` and `cml/` are independent, pure-numpy engines with no pygame imports. Every interaction between them goes through a `BoardCoupling` (`coupling/interface.py`). `World` (`sim/world.py`) calls its hooks: `on_piece_locked`, `on_life_step` and `on_cml_step`. New cross-engine mechanics belong in a coupling, not in an engine.

**Coupling selection.** `config.coupling.mode` picks the coupling through `make_coupling` in `sim/world.py`:
- `board_life` (default) is `BoardLifeCoupling`. The Tetris board *is* the Life grid. Every `locks_per_generation` locks, `board_life_step` (a pure function) evolves the visible surface, settles floating clusters, then calls `TetrisEngine.replace_board`, which clears and scores full rows and checks for block-out. This coupling sets `drives_life = True`, so `World` never seeds or time-steps the Life engine. `LifeEngine.record_generation` only mirrors the board and counts generations. The CML gates which cells a generation may change (`fertility_threshold`). That mask is snapshotted by `on_start` and after each `evolve`, never read live, because the chaotic CML flips most cells every step.
- `none` is `NullCoupling`. Life runs as a free random soup on its own timer.

**Adaptive difficulty (LPP).** `World.dispatch_lock_events` records the stack height after every lock. When the level goes up, `World._retune` calls `AdaptiveDifficulty.retune` (`optimization/adaptive.py`), which solves an LP and swaps in a new `coupling.config` with the new N and t. The LP's linear models are hard-coded coefficients in `AdaptiveConfig`, fitted by `scripts/fit_difficulty.py`. Refit them after changing anything that affects Life's difficulty. Bot sweeps must run with `AdaptiveConfig(enabled=False)` so that they measure fixed settings.

**Time model.** `app.py` runs a fixed-timestep loop (`sim_dt = 1/120`) with variable-rate rendering. `World.step` keeps a separate accumulator for Life and for CML, with `_EPS` tolerance for float drift. Pieces can lock in two places: from gravity inside `World.step`, or from player input (a hard drop) in `app.py`. The engine therefore queues `LockEvent`s, and `World.dispatch_lock_events()` is called from both places. Any new code path that can lock a piece must dispatch afterwards.

**Board conventions.** The board is an `np.uint8` array of shape `(hidden_rows + height, width)`. Row 0 is the top, and the first `hidden_rows` rows are the spawn buffer. Cell values are 0 for empty, 1–7 for `PieceType`, and 8 for `GARBAGE` (a cell born from Life). Board Life ignores hidden rows: they are not evolved and don't count as neighbours. Cells of the active piece are passed as `protected` so births never land on them.

**Config.** Every tunable constant lives in `config.py` as a frozen dataclass nested under `GameConfig`. Some validate in `__post_init__`. Build variants with `dataclasses.replace`; tests do this with seeded configs. `core/grid.py` provides the shared neighbour sums for the `fixed`, `periodic` and `reflective` boundaries.

## Open design questions: do not invent

These are intentionally stubs that raise `NotImplementedError`. Don't make up a model for them. Ask the user for the specification first.
- **Game Theory** (`strategy/interface.py`). Players, strategies and payoffs are undefined. `World.observation()` already builds the `GameObservation` input.

The coupling defaults (`locks_per_generation=8`, `surface_depth=1`, `settle="clusters"`) came from headless bot sweeps (`fertility_threshold=0.5` was checked with `scripts/balance_sweep.py`; see README *Balance*). Don't change these defaults without the user's agreement.
