# Evoltris
Combining Conway's Game of Life with Tetris to create an adaptive, strategy-driven game with dynamically evolving difficulty.

## Run
```sh
uv run evoltris      # play
uv run pytest        # tests
```
Controls: ←/→ move · ↓ soft drop · ↑/X rotate CW · Z rotate CCW · Space hard drop · G/C toggle Life/CML layers · P pause · R restart · Esc quit.

## Architecture (`src/evoltris/`)
| Module | Responsibility |
|---|---|
| `config.py` | All tunable constants (frozen dataclasses) |
| `core/grid.py` | Vectorised neighbour sums with `fixed` / `periodic` / `reflective` boundaries |
| `tetris/` | Pieces (SRS rotation + wall kicks), 7-bag randomizer, engine (gravity, lock delay, line clears, scoring) |
| `life/` | Conway's Game of Life, B3/S23, binary `uint8` grid |
| `cml/` | Coupled Map Lattice: continuous environmental grid in [0, 1] |
| `coupling/` | `BoardCoupling` protocol linking the engines; `NullCoupling` default |
| `strategy/` | Game Theory interface (stub) |
| `optimization/` | LPP difficulty-optimizer interface (stub) |
| `sim/world.py` | Owns the engines and steps each on its own fixed interval |
| `ui/`, `app.py` | pygame-ce rendering/input and a fixed-timestep main loop |

The engines have no pygame dependency and are unit-tested headlessly.

## Mathematics
**Game of Life**: with n the count of the 8 Moore neighbours, `next = (n == 3) | (alive & n == 2)`. Default boundary: `fixed` (outside cells are dead).

**CML** (Kaneko diffusive coupling, von Neumann neighbourhood):

    x'ᵢⱼ = (1 − ε)·f(xᵢⱼ) + (ε/4)·Σ_{4 nbrs} f(x_nbr),   f(x) = r·x·(1 − x)

With r ∈ [0, 4] and ε ∈ [0, 1], each update is a convex combination of values in [0, 1], so the state stays in [0, 1]. Defaults: r = 3.9 (chaotic regime), ε = 0.3, `reflective` (zero-flux) boundary. With `periodic` or `reflective` boundaries, coupling conserves Σ f(x).

The two grids are separate: the CML is an environmental layer and never sets the alive/dead state.

## Open design questions
These are intentionally left unimplemented until they are specified:
1. **GoL ↔ Tetris coupling.** How generations affect the board. Implement it as a `BoardCoupling`. For now the GoL runs on its own grid, drawn as an overlay.
2. **CML → gameplay.** How environmental values affect difficulty or mechanics.
3. **Game Theory.** Players, strategy sets, payoff function.
4. **LPP.** Decision variables, objective, constraints. `DifficultyProblem` already has the standard-form shape for a solver.
