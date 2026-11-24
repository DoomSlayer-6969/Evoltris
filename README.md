# Evoltris
Combining Conway's Game of Life with Tetris to create an adaptive, strategy-driven game with dynamically evolving difficulty.

## Run
```sh
uv run evoltris      # play
uv run pytest        # tests
```
Without uv: `pip install -r requirements.txt && pip install -e . && evoltris`. `requirements.txt` is exported from `uv.lock` and pins every dependency group (game, tests, report).

The technical report is [`docs/Evoltris_Report.pdf`](docs/Evoltris_Report.pdf). It explains how the game works and the mathematics behind it. To rebuild it (needs the Noto fonts in `/usr/share/fonts/noto`):
```sh
uv run --group report python docs/report/make_figures.py
uv run --group report python docs/report/build_report.py
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
| `strategy/` | Game Theory: zero-sum player-vs-director game, solved by LP |
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
Every number here comes from `scripts/balance_sweep.py`. A heuristic bot plays 24 seeded games per setting, capped at 500 pieces. A *naive* bot ignores Life. An *aware* bot scores its placements on the board the next generation will produce. The optimizer is off, so each row measures fixed settings. Coupling settings, with the fertility mask off to isolate them (`--table coupling`):

| Setting | Naive: losses / lines per piece | Aware: losses / lines per piece |
|---|---|---|
| No Life (`mode = "none"`) | 2/24 · 0.39 | 2/24 · 0.39 |
| Whole board, no settling, N=5 | 24/24 · 0.02 | 24/24 · 0.01 |
| Whole board, column settling, N=5 | 0/24 · 0.24 | 0/24 · 0.19 |
| **Depth 1, cluster settling, N=8 (default)** | **20/24 · 0.31** | **8/24 · 0.34** |
| Depth 1, cluster settling, N=5 | 24/24 · 0.27 | 9/24 · 0.31 |
| Depth 1, cluster settling, N=12 | 19/24 · 0.33 | 2/24 · 0.36 |

Without settling, dead blocks leave covered holes and the game is unplayable. Column settling makes Life a harmless eroder. With depth 1 and cluster settling, players who ignore the preview mostly lose and players who plan around it mostly survive. `locks_per_generation` is then a smooth difficulty knob (lower is harder), which makes it a natural LPP decision variable (see *Adaptive difficulty*).

**CML fertility mask** (`--table fertility`). At threshold 0.5 the mask does not clearly change the balance. The adaptive rows are the mask-on row rerun with `--adaptive` (the director row has the Game Theory director on; the row above it was measured before the director existed):

| Default coupling, N=8 | Naive: losses / lines per piece | Aware: losses / lines per piece |
|---|---|---|
| Fertility mask off | 20/24 · 0.31 | 8/24 · 0.34 |
| Fertility mask on (0.5, default) | 20/24 · 0.33 | 12/24 · 0.34 |
| Mask on + adaptive LPP, 50% limit | 16/24 · 0.34 | 5/24 · 0.34 |
| Mask on + adaptive LPP + director (default) | 14/24 · 0.35 | 7/24 · 0.34 |

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

## Game Theory director
The LPP decides *how hard* each level is. A zero-sum game decides *which kind* of hard. At each level-up the **director** picks a style of Life, a fertility threshold t, and the LPP then sets N with t fixed. As a result, every style has about the same predicted stack height:

| Director style | t | N at the default difficulty |
|---|---|---|
| rare & wide | 0.3 | 10 |
| balanced | 0.5 | 8 |
| frequent & narrow | 0.7 | 6 |

The **player**'s strategies are play styles, measured with bot policies from `scripts/balance_sweep.py`:
- `naive`: ignores Life.
- `aware`: plans on the lock that triggers a generation.
- `cautious`: also weighs a hypothetical generation on every other lock.
- `well`: keeps a column open for Tetrises.

The **payoff** is the player's survival rate A[i][j], from 48 games per cell (`scripts/fit_strategy.py`, about ±0.07 noise). The player maximises it and the director minimises it. The director's mixed Nash equilibrium y and the game value v come from one LP:

    minimise v   subject to   Σ_j A[i][j]·y_j ≤ v  for every player style i,   Σ_j y_j = 1,   y ≥ 0

The player's equilibrium comes from the dual LP, and both give the same v (minimax theorem). The director samples its style from y, so no player style can average better than v against it.

| Survival rate | rare & wide | balanced | frequent & narrow |
|---|---|---|---|
| naive | 0.25 | 0.15 | 0.15 |
| **aware** | 0.79 | 0.65 | **0.60** |
| cautious | 0.00 | 0.00 | 0.04 |
| well | 0.15 | 0.10 | 0.06 |

**The equilibrium is pure** (game value 0.60). `aware` beats every other style against every Life style, and against `aware`, frequent & narrow Life is the hardest. So the director always plays frequent & narrow. That reflects a real effect: at equal predicted stack height, frequent & narrow Life is harder to survive than rare & wide (0.60 vs 0.79), which the LPP's height model does not capture. The director only randomises if the payoff matrix has a trade-off, meaning player styles that are each best against a different kind of Life. Adding such styles to `StrategyConfig.player_styles` and to the bot, then rerunning `fit_strategy.py`, is all it takes. `cautious` is a weak heuristic, not a real playstyle.

`World.observation()` feeds `Director.evaluate`, which reports the game value and both mixes. The sidebar shows the current director style.
