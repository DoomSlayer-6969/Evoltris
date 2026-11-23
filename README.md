# Evoltris
Combining Conway's Game of Life with Tetris to create an adaptive, strategy-driven game with dynamically evolving difficulty.

## Run
```sh
uv run evoltris      # play
uv run pytest        # tests
```
Controls: ←/→ move · ↓ soft drop · ↑/X rotate CW · Z rotate CCW · Space hard drop · G toggle next-generation preview · C toggle CML layer · P pause · R restart · Esc quit.

## Architecture (`src/evoltris/`)
| Module | Responsibility |
|---|---|
| `config.py` | All tunable constants (frozen dataclasses) |
| `core/grid.py` | Vectorised neighbour sums with `fixed` / `periodic` / `reflective` boundaries |
| `tetris/` | Pieces (SRS rotation + wall kicks), 7-bag randomizer, engine (gravity, lock delay, line clears, scoring) |
| `life/` | Conway's Game of Life, B3/S23, binary `uint8` grid |
| `cml/` | Coupled Map Lattice: continuous environmental grid in [0, 1] |
| `coupling/` | `BoardCoupling` protocol linking the engines; `BoardLifeCoupling` (default) and `NullCoupling` |
| `strategy/` | Game Theory interface (stub) |
| `optimization/` | LPP difficulty-optimizer interface (stub) |
| `sim/world.py` | Owns the engines and steps each on its own fixed interval |
| `ui/`, `app.py` | pygame-ce rendering/input and a fixed-timestep main loop |

The engines have no pygame dependency and are unit-tested headlessly.

## Mathematics
**Game of Life**: with n the count of the 8 Moore neighbours, `next = (n == 3) | (alive & n == 2)`. Default boundary: `fixed` (outside cells are dead).

**Board ↔ Life coupling** (`coupling.mode = "board_life"`, default). The Tetris stack *is* the Life grid. After every `locks_per_generation` (default **8**) piece locks, one B3/S23 generation is applied to the visible board, with every occupied cell alive:
- a block with 2–3 occupied neighbours survives and keeps its piece colour;
- every other block dies, leaving a hole;
- an empty cell with exactly 3 occupied neighbours is born as a grey **garbage** block.

Only the **surface** evolves (`surface_depth`, default 1): cells within *K* rows of their column's top block, plus all open air above it. Deeper blocks are frozen but still count as neighbours. Blocks left floating then **settle** (`settle`, default `"clusters"`): each 4-connected group falls as a rigid body until it rests (sticky gravity). Hidden spawn rows are not evolved and do not count as neighbours. Births never land on the active piece. Rows completed by a generation are cleared and scored like normal line clears. The walls and floor count as dead (`fixed` boundary). In this mode the Life engine mirrors the board instead of running its own random soup, and **G** previews the next generation: hollow squares are births, dark dots are deaths (shown before settling). `mode = "none"` restores the independent overlay.

**CML** (Kaneko diffusive coupling, von Neumann neighbourhood):

    x'ᵢⱼ = (1 − ε)·f(xᵢⱼ) + (ε/4)·Σ_{4 nbrs} f(x_nbr),   f(x) = r·x·(1 − x)

With r ∈ [0, 4] and ε ∈ [0, 1], each update is a convex combination of values in [0, 1], so the state stays in [0, 1]. Defaults: r = 3.9 (chaotic regime), ε = 0.3, `reflective` (zero-flux) boundary. With `periodic` or `reflective` boundaries, coupling conserves Σ f(x).

The two grids are separate: the CML is an environmental layer and never sets the alive/dead state.

## Balance
The coupling defaults come from headless sweeps: a heuristic bot played 24 seeded games per setting, capped at 500 pieces. A *naive* bot ignores Life. An *aware* bot scores its placements on the board after the next generation. Without Life, the bot clears 0.39 lines per piece and survives.

| Setting | Naive: losses / lines per piece | Aware: losses / lines per piece |
|---|---|---|
| Whole board, no settling, N=5 | 8/8 · 0.02 | 8/8 · 0.01 |
| Whole board, column settling, N=5 | 0/8 · 0.25 | 0/8 · 0.20 |
| **Depth 1, cluster settling, N=8 (default)** | **20/24 · 0.31** | **2/24 · 0.35** |
| Depth 1, cluster settling, N=5 | 24/24 · 0.26 | 1/24 · 0.33 |
| Depth 1, cluster settling, N=12 | 15/24 · 0.33 | 0/24 · 0.36 |

Without settling, dead blocks leave covered holes and the game is unplayable. Column settling makes Life a harmless eroder. With depth 1 and cluster settling, players who ignore the preview lose and players who plan around it survive. `locks_per_generation` is then a smooth difficulty knob (lower is harder), which makes it a natural LPP decision variable.

## Open design questions
These are intentionally left unimplemented until they are specified:
1. ~~GoL ↔ Tetris coupling~~: resolved as `BoardLifeCoupling` (see above and *Balance* below).
2. **CML → gameplay.** How environmental values affect difficulty or mechanics.
3. **Game Theory.** Players, strategy sets, payoff function.
4. **LPP.** Decision variables, objective, constraints. `DifficultyProblem` already has the standard-form shape for a solver.
