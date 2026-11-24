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
| `optimization/` | LPP difficulty optimizer: `scipy` `linprog` backend and the adaptive controller |
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

The CML never sets the alive/dead state directly. In `board_life` mode it acts as a **fertility mask** (`fertility_threshold`, default **0.5**): a generation may only change cells whose CML value is above the threshold. Frozen cells still count as neighbours. At r = 3.9 the CML flips about 75% of that mask on every step, so the mask is snapshotted at game start and right after each generation. It then stays fixed for the next `locks_per_generation` locks, which keeps the **G** preview exact. With the board-life coupling, **C** shows this frozen mask (tinted cells can change) instead of the live heatmap. `fertility_threshold = None` or disabling the CML turns the mask off.

## Balance
The coupling defaults come from headless sweeps: a heuristic bot played 24 seeded games per setting, capped at 500 pieces. A *naive* bot ignores Life. An *aware* bot scores its placements on the board after the next generation. Without Life, the bot clears 0.39 lines per piece and survives.

| Setting | Naive: losses / lines per piece | Aware: losses / lines per piece |
|---|---|---|
| Whole board, no settling, N=5 | 8/8 · 0.02 | 8/8 · 0.01 |
| Whole board, column settling, N=5 | 0/8 · 0.25 | 0/8 · 0.20 |
| **Depth 1, cluster settling, N=8 (default)** | **20/24 · 0.31** | **2/24 · 0.35** |
| Depth 1, cluster settling, N=5 | 24/24 · 0.26 | 1/24 · 0.33 |
| Depth 1, cluster settling, N=12 | 15/24 · 0.33 | 0/24 · 0.36 |

Without settling, dead blocks leave covered holes and the game is unplayable. Column settling makes Life a harmless eroder. With depth 1 and cluster settling, players who ignore the preview lose and players who plan around it survive. `locks_per_generation` is then a smooth difficulty knob (lower is harder), which makes it a natural LPP decision variable (see *Adaptive difficulty*).

**CML fertility mask.** `scripts/balance_sweep.py` reproduces this setup: `uv run python scripts/balance_sweep.py --games 24`. Its aware bot is weaker than the one behind the table above: at the default setting with the mask off, it loses 8/24 instead of 2/24. With that bot, the fertility mask at threshold 0.5 does not clearly change the balance:

| Default coupling, N=8 | Naive: losses / lines per piece | Aware: losses / lines per piece |
|---|---|---|
| Fertility mask off | 20/24 · 0.31 | 8/24 · 0.34 |
| Fertility mask on (0.5, default) | 20/24 · 0.33 | 12/24 · 0.34 |
| Mask on + adaptive LPP, 50% limit (default) | 16/24 · 0.34 | 5/24 · 0.34 |

## Adaptive difficulty (LPP)
At every level-up (every 10 lines) a linear program re-tunes the two Life knobs: **N** = `locks_per_generation` ∈ [4, 12] (integer) and **t** = `fertility_threshold` ∈ [0.3, 0.7]. `scripts/fit_difficulty.py` fits two linear models from aware-bot sweeps over that grid (24 games per point, R² = 0.83 for both):

    height(N, t) = 10.27 − 0.221·N − 1.813·t     mean stack height in rows (higher is harder)
    loss(N, t)   = 0.955 − 0.054·N − 0.300·t     aware-bot loss rate

The player's mean stack height over the finished level, h, moves the target H* ← H* + 0.5·(7 − h). A stack below 7 rows means the player is comfortable, so the target rises. Then the LP is solved:

    minimise s   subject to   |height(N, t) − H*| ≤ s,   loss(N, t) ≤ 0.5,   bounds

The absolute value is written as two linear inequalities. N is rounded by re-solving with N fixed to the floor and to the ceiling of its relaxed value. H* is clamped to the heights the fair region can reach, so it cannot wind up. The new t takes effect at the next fertility snapshot. All of this lives in `AdaptiveConfig`, which only works with the board-life coupling and a fertility threshold.

**Choosing the fairness limit.** The easiest fair setting is always N = 12, t = 0.7. The limit only decides how hard the game can get for players who are doing well. With the optimizer on, the aware bot loses about 5–7/24 at every limit, because the adaptive target holds its stack near 7.5 rows. The limit mainly sets how costly it is to ignore Life, and how far the settings can swing from one level to the next (24 bot games per row; level 0 uses the coupling defaults):

| Limit | N range used | Largest one-level jump in N | Naive losses | Aware losses |
|---|---|---|---|---|
| 15% | 12 | 0 | 9/24 | 5/24 |
| 25% | 11–12 | 1 | 16/24 | 7/24 |
| 35% | 9–12 | 3 | 13/24 | 6/24 |
| **50% (default)** | 7–12 | 5 | 16/24 | 5/24 |
| ≥ 65% (no limit) | 4–12 | 8 | 21/24 | 7/24 |

50% gives the largest and most frequent swings a planning player still survives. Without a limit, the game is simply harder: the aware bot's stack rises to 8.1 rows.

## Open design questions
These are intentionally left unimplemented until they are specified:
1. ~~GoL ↔ Tetris coupling~~: resolved as `BoardLifeCoupling` (see above and *Balance* below).
2. ~~CML → gameplay~~: resolved as the fertility mask (see *Mathematics*).
3. **Game Theory.** Players, strategy sets, payoff function.
4. ~~LPP~~: resolved as the adaptive difficulty controller (see *Adaptive difficulty*).
