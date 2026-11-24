"""Figures for the Evoltris report, generated from the game's own code.

Run from the repository root (it imports the bot from ``scripts/``):

    uv run --group report python docs/report/make_figures.py [out_dir]

``out_dir`` defaults to ``docs/report/fig``. Needs the Noto fonts
(NotoSans, NotoSansMath) under /usr/share/fonts/noto.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, "scripts")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap, ListedColormap
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/report/fig")
OUT.mkdir(parents=True, exist_ok=True)

# ---- style (light, print) --------------------------------------------------
for f in ("NotoSans-Regular.ttf", "NotoSans-Bold.ttf", "NotoSans-Italic.ttf", "NotoSansMath-Regular.ttf"):
    font_manager.fontManager.addfont(f"/usr/share/fonts/noto/{f}")
TEXT, TEXT2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
SURFACE = "#ffffff"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update(
    {
        "font.family": ["Noto Sans", "Noto Sans Math"],
        "font.size": 9,
        "text.color": TEXT,
        "axes.labelcolor": TEXT2,
        "axes.edgecolor": MUTED,
        "xtick.color": TEXT2,
        "ytick.color": TEXT2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.dpi": 220,
        "savefig.bbox": "tight",
    }
)
SEQ = LinearSegmentedColormap.from_list("seq", ["#eef4fc", "#9cc0ee", BLUE, "#123f78"])

from evoltris.cml.engine import CMLEngine  # noqa: E402
from evoltris.config import (  # noqa: E402
    AdaptiveConfig,
    CMLConfig,
    GameConfig,
    RenderConfig,
    TetrisConfig,
)
from evoltris.coupling.board_life import board_life_step  # noqa: E402
from evoltris.tetris.pieces import GARBAGE, PieceType  # noqa: E402
from evoltris.ui.renderer import PIECE_COLOURS  # noqa: E402

CELL_RGB = {k: tuple(c / 255 for c in v) for k, v in PIECE_COLOURS.items()}
CELL_RGB[GARBAGE] = (0.55, 0.55, 0.58)


# ---- Fig 1: in-game screenshot ---------------------------------------------
def screenshot():
    import pygame
    from balance_sweep import evaluate, placements

    from evoltris.sim.world import World
    from evoltris.ui.renderer import Renderer

    cfg = GameConfig(tetris=TetrisConfig(seed=3), cml=CMLConfig(seed=3), render=RenderConfig())
    w = World(cfg)
    t, cp = w.tetris, w.coupling
    hidden = cfg.board.hidden_rows
    # Let the bot play until a generation is one lock away on a mid-sized stack.
    for n in range(400):
        best, bv = None, -1e18
        for cand in placements(t):
            b = t.board.copy()
            for r, c in cand.cells():
                b[r, c] = int(cand.type)
            v = evaluate(b, hidden)
            if v > bv:
                best, bv = cand, v
        t.active = best
        t.hard_drop()
        w.dispatch_lock_events()
        for _ in range(4):
            w.cml.step()
        if n > 60 and cp.locks_until_generation == 1 and 6 <= t.stack_height <= 9:
            before, after = cp.preview(t, settle=False), t.board
            changes = int(((before != 0) != (after != 0))[hidden:].sum())
            if changes >= 5:
                break
    pygame.init()
    r = Renderer(w, cfg.render)
    surf = pygame.Surface(r.size)
    r.draw(surf, w)
    pygame.image.save(surf, str(OUT / "screenshot.png"))
    pygame.quit()
    return {"level": t.level, "lines": t.lines, "score": t.score}


# ---- Fig 2: one board generation -------------------------------------------
def board_panel(ax, vis, title, born=None, dies=None):
    h, wdt = vis.shape
    ax.set_xlim(0, wdt)
    ax.set_ylim(h, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    for r in range(h):
        for c in range(wdt):
            ax.add_patch(Rectangle((c, r), 1, 1, fc="#f4f4f2", ec="#dcdbd6", lw=0.5))
            v = int(vis[r, c])
            if v:
                ax.add_patch(
                    Rectangle((c + 0.06, r + 0.06), 0.88, 0.88, fc=CELL_RGB[v], ec="none")
                )
    if born is not None:
        for r, c in zip(*np.nonzero(born)):
            ax.add_patch(
                Rectangle((c + 0.06, r + 0.06), 0.88, 0.88, fc="none", ec=TEXT, lw=1.4, ls="--")
            )
    if dies is not None:
        for r, c in zip(*np.nonzero(dies)):
            ax.plot([c + 0.25, c + 0.75], [r + 0.25, r + 0.75], color=TEXT, lw=1.6)
            ax.plot([c + 0.25, c + 0.75], [r + 0.75, r + 0.25], color=TEXT, lw=1.6)
    ax.set_title(title, fontsize=9.5, color=TEXT, pad=6)


def life_figure():
    H, W, HID = 22, 10, 2
    b = np.zeros((H, W), dtype=np.uint8)
    rows = {
        13: "......J...",
        14: ".....JJJ..",
        15: "..T.......",
        16: ".TTT..OO..",
        17: "SS.ZZ.OO.L",
        18: "IIII.ZZLLL",
        19: "SS.SSIIII.",
        20: ".SSSS.TTT.",
        21: "LLLZZ.JJTL",
    }
    code = {ch: int(getattr(PieceType, ch)) for ch in "IOTSZJL"}
    for r, s in rows.items():
        for c, ch in enumerate(s):
            if ch != ".":
                b[r, c] = code[ch]
    raw = board_life_step(b, HID, surface_depth=1, settle="none")
    settled = board_life_step(b, HID, surface_depth=1, settle="clusters")
    top = 12
    vis, rv, sv = b[top:], raw[top:], settled[top:]
    born, dies = (vis == 0) & (rv != 0), (vis != 0) & (rv == 0)
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.55))
    board_panel(axes[0], vis, "(a) Before (changes marked)", born, dies)
    board_panel(axes[1], rv, "(b) After B3/S23 on the surface")
    board_panel(axes[2], sv, "(c) After cluster settling")
    fig.text(
        0.5,
        0.0,
        "Dashed outline: cell is born as grey garbage.   ×: block dies.   "
        "Deeper blocks are frozen but still count as neighbours.",
        ha="center",
        color=TEXT2,
        fontsize=8,
    )
    fig.savefig(OUT / "life.png")
    plt.close(fig)
    return int(born.sum()), int(dies.sum())


# ---- Fig 3: CML chaos and the snapshot -------------------------------------
def cml_figure():
    e = CMLEngine((22, 10), CMLConfig(seed=0))
    e.randomize()
    for _ in range(50):
        e.step()
    s0 = e.state.copy()
    e.step()
    s1 = e.state.copy()
    e2 = CMLEngine((22, 10), CMLConfig(seed=0))
    e2.randomize()
    for _ in range(50):
        e2.step()
    m0 = e2.state > 0.5
    lags, same = [], []
    for k in range(1, 13):
        e2.step()
        lags.append(k)
        same.append(float(((e2.state > 0.5) == m0).mean()))

    fig = plt.figure(figsize=(7.2, 3.1))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1.9], wspace=0.55)
    mask_cmap = ListedColormap(["#f4f4f2", "#1f6b5e"])
    for i, (s, title) in enumerate(((s0, "(a) Fertile mask, step k"), (s1, "(b) Step k + 1"))):
        ax = fig.add_subplot(gs[0, i])
        ax.imshow(s[2:] > 0.5, cmap=mask_cmap, interpolation="nearest")
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(True)
            sp.set_color(MUTED)
        ax.set_title(title, fontsize=9.5, pad=6)
    ax = fig.add_subplot(gs[0, 2])
    ax.plot(lags, same, color=BLUE, lw=2, marker="o", ms=4.5, mec=SURFACE, mew=1.2)
    ax.axhline(0.5, color=MUTED, lw=1, ls=":")
    ax.text(12.3, 0.5, "chance", va="center", color=MUTED, fontsize=8)
    ax.set_ylim(0, 1)
    ax.set_xlim(0.5, 12.5)
    ax.set_xticks(range(1, 13))
    ax.set_xlabel("Steps after step k (0.25 s each)")
    ax.set_ylabel("Same mask as step k")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_title("(c) The live mask flickers (r = 3.9)", fontsize=9.5, pad=6)
    fig.savefig(OUT / "cml.png")
    plt.close(fig)
    return same[0], float((s0 > 0.5).mean())


# ---- Fig 4: the LP's decision space ----------------------------------------
def lpp_figure():
    c = AdaptiveConfig()
    h, loss = c.height_model, c.loss_model
    n = np.linspace(4, 12, 300)
    t = np.linspace(0.3, 0.7, 300)
    N, T = np.meshgrid(n, t)
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    fair = loss(N, T) <= c.max_aware_loss
    ax.contourf(N, T, fair, levels=[0.5, 1.5], colors=["#e3eefb"])
    cs = ax.contour(N, T, h(N, T), levels=np.arange(7.0, 9.0, 0.5), colors=MUTED, linewidths=0.8)
    ax.clabel(cs, fmt=lambda v: f"{v:.1f} rows", fontsize=7, colors=TEXT2)
    # Loss = limit boundary: t = (l0 + lN*N - limit) / -lt
    tb = (loss.intercept + loss.n * n - c.max_aware_loss) / -loss.t
    ok = (tb >= 0.3) & (tb <= 0.7)
    ax.plot(n[ok], tb[ok], color=BLUE, lw=2)
    ax.text(5.05, 0.665, "predicted loss = 50%\n(fairness limit)", color=BLUE, fontsize=8)
    ax.text(10.3, 0.58, "fair region", color="#123f78", fontsize=9, fontweight="bold")
    ax.text(4.3, 0.33, "unfair", color=TEXT2, fontsize=9)
    pts = [
        ((8, 0.5), "start (N=8, t=0.5)", (8.15, 0.515)),
        ((7, 0.30), "hardest fair (7, 0.30)", (7.15, 0.315)),
        ((12, 0.7), "easiest (12, 0.70)", (10.55, 0.655)),
    ]
    for (x, y), label, (lx, ly) in pts:
        ax.plot(x, y, "o", color=ORANGE, ms=7, mec=SURFACE, mew=1.5, zorder=5, clip_on=False)
        ax.text(lx, ly, label, fontsize=8, color=TEXT)
    ax.set_xlabel("N: locks per generation (higher is easier)")
    ax.set_ylabel("t: fertility threshold (higher is easier)")
    ax.set_xlim(4, 12)
    ax.set_ylim(0.3, 0.7)
    ax.set_title(
        "Grey contours: predicted stack height. Shaded: settings the LP may choose.",
        fontsize=9,
        color=TEXT2,
        loc="left",
    )
    fig.savefig(OUT / "lpp.png")
    plt.close(fig)


# ---- Fig 5: architecture and level-up flow ---------------------------------
def box(ax, x, y, w, h, text, fc="#f4f4f2", ec=MUTED, bold=False, size=8.2):
    ax.add_patch(
        FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02", fc=fc, ec=ec, lw=1)
    )
    ax.text(
        x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size,
        fontweight="bold" if bold else "normal", color=TEXT, linespacing=1.3,
    )


def arrow(ax, a, b, color=MUTED):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=10, color=color, lw=1.1))


def architecture_figure():
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    eng = "#e3eefb"
    box(ax, 0.02, 0.56, 0.22, 0.24, "Tetris engine\npieces, gravity,\nline clears, scoring", fc=eng)
    box(ax, 0.02, 0.10, 0.22, 0.24, "CML engine\nlogistic map +\ndiffusive coupling", fc=eng)
    box(ax, 0.39, 0.33, 0.24, 0.30, "Board–Life coupling\nevery N locks: one\nB3/S23 generation on\nthe fertile surface", fc="#e8f6f0")
    box(ax, 0.76, 0.56, 0.22, 0.24, "LPP optimizer\nchooses N\nat each level-up", fc="#fdeee7")
    box(ax, 0.76, 0.10, 0.22, 0.24, "Game Theory director\nchooses the style\nof Life (t)", fc="#fdeee7")
    # Tetris <-> coupling
    arrow(ax, (0.245, 0.66), (0.385, 0.56))
    ax.text(0.315, 0.65, "piece locks", fontsize=7.5, color=TEXT2, ha="left", va="bottom")
    arrow(ax, (0.385, 0.50), (0.245, 0.60))
    ax.text(0.30, 0.50, "evolved board", fontsize=7.5, color=TEXT2, ha="center", va="top")
    # CML -> coupling
    arrow(ax, (0.245, 0.24), (0.385, 0.38))
    ax.text(0.318, 0.255, "fertile mask\n(snapshot)", fontsize=7.5, color=TEXT2, ha="center", va="top")
    # Tetris -> LPP (top), LPP -> coupling, director -> LPP
    ax.plot([0.13, 0.13, 0.87], [0.815, 0.90, 0.90], color="#b9b8b2", lw=1.1)
    arrow(ax, (0.87, 0.90), (0.87, 0.815), color="#b9b8b2")
    ax.text(0.5, 0.915, "stack height after every lock; level-ups", fontsize=7.5, color=TEXT2, ha="center")
    arrow(ax, (0.755, 0.62), (0.635, 0.55))
    ax.text(0.70, 0.62, "N, t", fontsize=7.5, color=TEXT2)
    arrow(ax, (0.87, 0.345), (0.87, 0.555))
    ax.text(0.88, 0.44, "t", fontsize=7.5, color=TEXT2)
    ax.text(0.5, 0.0, "World owns every engine and steps each on its own fixed timestep; "
            "the engines never call each other directly.", ha="center", fontsize=7.8, color=TEXT2)
    fig.savefig(OUT / "architecture.png")
    plt.close(fig)


def levelup_figure():
    steps = [
        "1  Level-up\n(every 10 lines)",
        "2  Measure h: the player's\nmean stack height\nduring the last level",
        "3  Update the target\nH* ← H* + 0.5·(7 − h),\nclamped to the fair range",
        "4  Director samples a style\nof Life (t) from its\nNash equilibrium",
        "5  LP picks the integer N\nclosest to H* for that t,\nwith predicted loss ≤ 50%",
        "6  Apply N now; the new t\ntakes effect at the next\nfertility snapshot",
    ]
    fig, ax = plt.subplots(figsize=(7.2, 2.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    w, h, gap = 0.29, 0.36, 0.065
    xs = [0.005 + i * (w + gap) for i in range(3)]
    ys = [0.56, 0.04]
    for i, txt in enumerate(steps):
        x, y = xs[i % 3], ys[i // 3]
        fc = "#fdeee7" if i in (3, 4) else "#f4f4f2"
        box(ax, x, y, w, h, txt, fc=fc, size=7.8)
        if i % 3:
            arrow(ax, (x - gap + 0.008, y + h / 2), (x - 0.008, y + h / 2))
    # row 1 end -> row 2 start
    mid = (ys[0] + ys[1] + h) / 2
    x3, x4 = xs[2] + w / 2, xs[0] + w / 2
    ax.plot([x3, x3, x4, x4], [ys[0] - 0.012, mid, mid, mid], color=MUTED, lw=1.1)
    arrow(ax, (x4, mid), (x4, ys[1] + h + 0.012))
    fig.savefig(OUT / "levelup.png")
    plt.close(fig)


if __name__ == "__main__":
    print("screenshot state:", screenshot())
    print("life born/dies:", life_figure())
    print("cml same-after-1-step, fertile share:", cml_figure())
    lpp_figure()
    architecture_figure()
    levelup_figure()
    print("figures in", OUT)
