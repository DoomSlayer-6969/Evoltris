"""Build the Evoltris technical report (PDF) with ReportLab.

Run from the repository root after ``make_figures.py``:

    uv run --group report python docs/report/build_report.py [fig_dir] [out_pdf]

Defaults: ``docs/report/fig`` and ``docs/Evoltris_Report.pdf``. Needs the
Noto fonts (NotoSerif, NotoSans, NotoSansMono, NotoSansMath) under
/usr/share/fonts/noto. The numbers in the text come from the measurements
described in the README; update them here if the balance changes.
"""

import sys
from pathlib import Path

from fontTools.ttLib import TTFont as FTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

FIG = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/report/fig")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/Evoltris_Report.pdf")

# --------------------------------------------------------------------- fonts
NOTO = "/usr/share/fonts/noto/"
for name, file in {
    "Serif": "NotoSerif-Regular.ttf",
    "Serif-Bold": "NotoSerif-Bold.ttf",
    "Serif-Italic": "NotoSerif-Italic.ttf",
    "Sans": "NotoSans-Regular.ttf",
    "Sans-Bold": "NotoSans-Bold.ttf",
    "Sans-Italic": "NotoSans-Italic.ttf",
    "Sans-BoldItalic": "NotoSans-BoldItalic.ttf",
    "Mono": "NotoSansMono-Regular.ttf",
    "Mono-Bold": "NotoSansMono-Bold.ttf",
    "Math": "NotoSansMath-Regular.ttf",
}.items():
    pdfmetrics.registerFont(TTFont(name, NOTO + file))
pdfmetrics.registerFontFamily(
    "Serif", normal="Serif", bold="Serif-Bold", italic="Serif-Italic", boldItalic="Serif-Bold"
)
pdfmetrics.registerFontFamily(
    "Sans", normal="Sans", bold="Sans-Bold", italic="Sans-Italic", boldItalic="Sans-BoldItalic"
)
pdfmetrics.registerFontFamily("Mono", normal="Mono", bold="Mono-Bold", italic="Mono", boldItalic="Mono-Bold")

_SERIF_CMAP = set(FTFont(NOTO + "NotoSerif-Regular.ttf").getBestCmap())
_SANS_CMAP = set(FTFont(NOTO + "NotoSans-Regular.ttf").getBestCmap())
_MONO_CMAP = set(FTFont(NOTO + "NotoSansMono-Regular.ttf").getBestCmap())


def mathfix(text: str, cmap=_SERIF_CMAP) -> str:
    """Wrap characters the text font lacks (≤, ←, ∈ ...) in the math font."""
    out = []
    for ch in text:
        if ord(ch) > 127 and ord(ch) not in cmap:
            out.append(f'<font name="Math">{ch}</font>')
        else:
            out.append(ch)
    return "".join(out)


# -------------------------------------------------------------------- colours
INK = colors.HexColor("#0b0b0b")
INK2 = colors.HexColor("#52514e")
MUTED = colors.HexColor("#8a8984")
RULE = colors.HexColor("#d9d8d3")
ACCENT = colors.HexColor("#1f5fae")
TINT = colors.HexColor("#eef4fc")
SOFT = colors.HexColor("#f6f6f4")
WARM = colors.HexColor("#fdf1eb")

# --------------------------------------------------------------------- styles
S = {}
S["body"] = ParagraphStyle(
    "body", fontName="Serif", fontSize=10.2, leading=15.2, textColor=INK, alignment=TA_JUSTIFY,
    spaceAfter=7,
)
S["bullet"] = ParagraphStyle(
    "bullet", parent=S["body"], leftIndent=16, bulletIndent=5, spaceAfter=3.5, alignment=TA_LEFT
)
S["h1"] = ParagraphStyle(
    "h1", fontName="Sans-Bold", fontSize=17, leading=22, textColor=INK, spaceBefore=4, spaceAfter=10,
    keepWithNext=1,
)
S["h2"] = ParagraphStyle(
    "h2", fontName="Sans-Bold", fontSize=12.6, leading=17, textColor=INK, spaceBefore=12, spaceAfter=5,
    keepWithNext=1,
)
S["h3"] = ParagraphStyle(
    "h3", fontName="Sans-Bold", fontSize=10.4, leading=14, textColor=ACCENT, spaceBefore=8, spaceAfter=3,
    keepWithNext=1,
)
S["eq"] = ParagraphStyle(
    "eq", fontName="Serif", fontSize=10.6, leading=16, alignment=TA_CENTER, spaceBefore=3, spaceAfter=9,
    textColor=INK,
)
S["caption"] = ParagraphStyle(
    "caption", fontName="Sans", fontSize=8.4, leading=11.6, textColor=INK2, alignment=TA_LEFT,
    spaceBefore=4, spaceAfter=12,
)
S["cell"] = ParagraphStyle("cell", fontName="Sans", fontSize=8.4, leading=11, textColor=INK)
S["cellb"] = ParagraphStyle("cellb", parent=S["cell"], fontName="Sans-Bold")
S["callout"] = ParagraphStyle(
    "callout", fontName="Sans", fontSize=9.2, leading=13.4, textColor=INK, alignment=TA_LEFT
)
S["code"] = ParagraphStyle(
    "code", fontName="Mono", fontSize=8.4, leading=12, textColor=INK, alignment=TA_LEFT
)
S["ref"] = ParagraphStyle(
    "ref", parent=S["body"], fontSize=9.2, leading=13, leftIndent=18, firstLineIndent=-18,
    alignment=TA_LEFT, spaceAfter=4,
)

FRAME_W = A4[0] - 2 * 2.3 * cm


def P(text, style="body"):
    st = S[style]
    cmap = _SANS_CMAP if st.fontName.startswith("Sans") else _SERIF_CMAP
    return Paragraph(mathfix(text, cmap), st)


def bullets(items, style="bullet"):
    return [Paragraph(mathfix(t), S[style], bulletText="•") for t in items]


def eq(text):
    return P(text, "eq")


def h1(text):
    return Paragraph(text, S["h1"])


def h2(text):
    return Paragraph(text, S["h2"])


def h3(text):
    return Paragraph(text, S["h3"])


_fig_no = [0]
_tab_no = [0]


def figure(name, caption, width=FRAME_W):
    _fig_no[0] += 1
    path = FIG / name
    img = Image(str(path))
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = width, width * ratio
    img.hAlign = "CENTER"
    cap = P(f"<b>Figure {_fig_no[0]}.</b> {caption}", "caption")
    return KeepTogether([Spacer(1, 4), img, cap])


def table(rows, widths, caption=None, header=True, bold_rows=(), align_right_from=None, zebra=True):
    data = []
    for i, row in enumerate(rows):
        st = S["cellb"] if (header and i == 0) or i in bold_rows else S["cell"]
        data.append([Paragraph(mathfix(str(c).replace("& ", "&amp; "), _SANS_CMAP), st) for c in row])
    t = Table(data, colWidths=widths, hAlign="CENTER", repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, -1), (-1, -1), 0.8, MUTED),
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, MUTED),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), TINT), ("LINEBELOW", (0, 0), (-1, 0), 0.6, MUTED)]
    if zebra:
        for r in range(1 if header else 0, len(rows)):
            if (r - (1 if header else 0)) % 2 == 1:
                style.append(("BACKGROUND", (0, r), (-1, r), SOFT))
    for r in bold_rows:
        style.append(("BACKGROUND", (0, r), (-1, r), WARM))
    t.setStyle(TableStyle(style))
    out = [t]
    if caption:
        _tab_no[0] += 1
        out.append(P(f"<b>Table {_tab_no[0]}.</b> {caption}", "caption"))
    return KeepTogether([Spacer(1, 3), *out])


def callout(title, text, tint=TINT, bar=ACCENT):
    body = Paragraph(mathfix(f"<b>{title}</b>  {text}", _SANS_CMAP), S["callout"])
    t = Table([[body]], colWidths=[FRAME_W])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), tint),
                ("LINEBEFORE", (0, 0), (0, -1), 3, bar),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return KeepTogether([Spacer(1, 2), t, Spacer(1, 9)])


def code(lines):
    body = Paragraph("<br/>".join(mathfix(l.replace(" ", "&nbsp;"), _MONO_CMAP) for l in lines), S["code"])
    t = Table([[body]], colWidths=[FRAME_W])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return KeepTogether([t, Spacer(1, 9)])


# ------------------------------------------------------------------ document
class ReportDoc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, pagesize=A4, **kw)
        m = 2.3 * cm
        frame = Frame(m, 2.2 * cm, A4[0] - 2 * m, A4[1] - 2.2 * cm - 2.4 * cm, id="body")
        title_frame = Frame(m, 2.2 * cm, A4[0] - 2 * m, A4[1] - 4.4 * cm, id="title")
        self.addPageTemplates(
            [
                PageTemplate("title", [title_frame], onPage=self._title_page),
                PageTemplate("body", [frame], onPage=self._body_page),
            ]
        )
        self._heading_no = 0

    def _title_page(self, canv, doc):
        canv.saveState()
        canv.setFillColor(ACCENT)
        canv.rect(0, A4[1] - 0.55 * cm, A4[0], 0.55 * cm, stroke=0, fill=1)
        canv.restoreState()

    def _body_page(self, canv, doc):
        canv.saveState()
        m = 2.3 * cm
        canv.setStrokeColor(RULE)
        canv.setLineWidth(0.6)
        canv.line(m, A4[1] - 1.75 * cm, A4[0] - m, A4[1] - 1.75 * cm)
        canv.setFont("Sans", 8)
        canv.setFillColor(INK2)
        canv.drawString(m, A4[1] - 1.55 * cm, "Evoltris — Technical Report")
        canv.drawRightString(A4[0] - m, A4[1] - 1.55 * cm, "November 2026")
        canv.line(m, 1.6 * cm, A4[0] - m, 1.6 * cm)
        canv.drawCentredString(A4[0] / 2, 1.1 * cm, f"{doc.page}")
        canv.restoreState()

    def beforeDocument(self):
        self._heading_no = 0  # multiBuild lays out several passes; keys must match

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        style = flowable.style.name
        if style not in ("h1", "h2"):
            return
        text = flowable.getPlainText()
        level = 0 if style == "h1" else 1
        self._heading_no += 1
        key = f"h{self._heading_no}"
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
        self.notify("TOCEntry", (level, text, self.page, key))


def build():
    story = []

    # ---------------------------------------------------------------- title
    story += [
        Spacer(1, 2.2 * cm),
        Paragraph("TECHNICAL REPORT", ParagraphStyle("kicker", fontName="Sans-Bold", fontSize=10,
                                                     textColor=ACCENT, leading=14)),
        Spacer(1, 6),
        Paragraph("Evoltris", ParagraphStyle("title", fontName="Sans-Bold", fontSize=40, leading=46,
                                             textColor=INK)),
        Spacer(1, 6),
        Paragraph(
            "Tetris on a living board: Conway’s Game of Life, chaotic coupled map lattices, "
            "linear programming and game theory in one game",
            ParagraphStyle("subtitle", fontName="Sans", fontSize=14.5, leading=20, textColor=INK2),
        ),
        Spacer(1, 0.9 * cm),
    ]
    img = Image(str(FIG / "screenshot.png"))
    w = 9.2 * cm
    img.drawWidth, img.drawHeight = w, w * img.imageHeight / img.imageWidth
    img.hAlign = "LEFT"
    story += [img, Spacer(1, 0.35 * cm)]
    story.append(
        Paragraph(
            "Evoltris during play (level 3): the teal cells are where the next Life generation may "
            "act; dots and hollow squares preview the blocks it will kill and create.",
            ParagraphStyle("tcap", parent=S["caption"], fontSize=8.6),
        )
    )
    story += [
        Spacer(1, 0.9 * cm),
        Table(
            [
                [Paragraph("Date", S["cellb"]), Paragraph("November 2026", S["cell"])],
                [Paragraph("Software version", S["cellb"]), Paragraph("commit ef6ec58 (main)", S["cell"])],
                [Paragraph("Implementation", S["cellb"]),
                 Paragraph("Python 3.14 · NumPy · SciPy (HiGHS) · pygame-ce · 145 automated tests", S["cell"])],
            ],
            colWidths=[3.6 * cm, FRAME_W - 3.6 * cm],
            hAlign="LEFT",
            style=TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.8, MUTED),
                              ("LINEBELOW", (0, -1), (-1, -1), 0.8, MUTED),
                              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0)]),
        ),
        NextPageTemplate("body"),
        PageBreak(),
    ]

    # ------------------------------------------------------------- summary + toc
    story.append(Paragraph("Summary", S["h1"]))
    story.append(P(
        "Evoltris is a falling-block puzzle game in which the stack the player builds is alive. "
        "Every few placed pieces, the blocks on the board are treated as cells of Conway’s Game of "
        "Life and advance one generation: isolated or overcrowded blocks die and leave holes, and "
        "empty cells with exactly three neighbours fill with grey garbage. Where the rule may act is "
        "decided by a chaotic coupled map lattice, and how often and how widely it acts is re-tuned at "
        "every level by a linear program that watches how comfortably the player is coping. A "
        "zero-sum game between the player and a difficulty “director” decides which kind of Life the "
        "player faces."
    ))
    story.append(P(
        "This report explains how the game works, gives a short overview of each mathematical concept it "
        "relies on, and shows precisely how each concept is used in the implementation. All numbers "
        "come from the shipped code: balance figures were measured with heuristic bots in seeded, "
        "reproducible headless games."
    ))
    story += bullets([
        "<b>Planning around Life pays off.</b> With every system enabled, a bot that ignores Life loses "
        "14 of 24 games; a bot that plans for the next generation loses 7 of 24.",
        "<b>The difficulty adapts.</b> A linear program fitted from 600 bot games (R² = 0.83) keeps the "
        "planning bot near a 7–8 row stack and its predicted loss rate at or below 50%.",
        "<b>Game theory finds a real effect.</b> At equal predicted difficulty, frequent-but-narrow Life "
        "is harder to survive than rare-but-wide Life (survival 0.60 vs 0.79), so the director’s "
        "equilibrium strategy is to always choose it.",
    ])
    story.append(PageBreak())
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("toc0", fontName="Sans-Bold", fontSize=10.2, leading=14, leftIndent=0,
                       firstLineIndent=0, spaceBefore=7, textColor=INK),
        ParagraphStyle("toc1", fontName="Sans", fontSize=9.4, leading=13.5, leftIndent=16,
                       firstLineIndent=0, textColor=INK2),
    ]
    toc.dotsMinLevel = 0
    story += [Paragraph("Contents", ParagraphStyle("tochead", parent=S["h1"])), toc, PageBreak()]

    # ------------------------------------------------------------- 1 intro
    story.append(h1("1  Introduction"))
    story.append(P(
        "Classic Tetris is a game of perfect information about a static board: once a block is placed "
        "it stays exactly where it is until a line clear removes it. Evoltris asks what happens if the "
        "board itself has dynamics. Its stated goal is to combine Conway’s Game of Life with Tetris to "
        "create <i>an adaptive, strategy-driven game with dynamically evolving difficulty</i>. Each "
        "part of that goal is delivered by a different branch of mathematics:"
    ))
    story.append(table(
        [
            ["Design goal", "Mechanism in the game", "Mathematics"],
            ["A living board", "The stack evolves as a Life grid every N locks", "Cellular automata (Conway’s Game of Life)"],
            ["Unpredictable but plannable environment", "A fertility mask decides where Life may act", "Chaos: logistic map, coupled map lattices"],
            ["Adaptive difficulty", "N and t are re-tuned at each level-up", "Least-squares regression, linear programming"],
            ["Strategy-driven play", "A director chooses the kind of Life to face", "Two-player zero-sum games, Nash equilibrium"],
        ],
        [4.0 * cm, 6.3 * cm, FRAME_W - 10.3 * cm],
        caption="How the design goals map to mathematical concepts.",
    ))
    story.append(P(
        "Section 2 describes the game from the player’s point of view. Section 3 summarises the "
        "software architecture. Section 4 is the core of the report: for each concept it gives an "
        "overview of the mathematics and then explains exactly how Evoltris uses it. Section 5 "
        "presents the measured balance results, Section 6 discusses limitations, and the appendices "
        "list the configuration parameters and the commands that reproduce every number."
    ))

    # ------------------------------------------------------------- 2 how it works
    story.append(CondPageBreak(10 * cm))
    story.append(h1("2  How the game works"))
    story.append(h2("2.1  The Tetris foundation"))
    story.append(P(
        "The playfield is 10 columns wide and 20 rows tall, with two hidden rows above the top where "
        "new pieces appear. The seven standard tetrominoes (I, O, T, S, Z, J, L) are dealt from a "
        "<i>7-bag</i>: each consecutive group of seven pieces contains every shape exactly once, in a "
        "shuffled order. The next three pieces are shown in the sidebar. Pieces rotate with the "
        "Super Rotation System (SRS), which tries a short list of offsets (“wall kicks”) when a "
        "rotation would otherwise collide. There is no hold piece."
    ))
    story.append(P(
        "Pieces fall one row every 0.8 s at level 0; the interval is multiplied by 0.85 at each level, "
        "down to a floor of 0.05 s. A piece that touches down locks after 0.5 s, and moving or "
        "rotating it resets that timer up to 15 times. A row clears when all ten cells are filled, "
        "and the player levels up every 10 cleared lines."
    ))
    story.append(table(
        [
            ["Action", "Points"],
            ["Clear 1 / 2 / 3 / 4 lines at once", "100 / 300 / 500 / 800, multiplied by (level + 1)"],
            ["Soft drop", "+1 per row"],
            ["Hard drop", "+2 per row"],
        ],
        [6.0 * cm, FRAME_W - 6.0 * cm],
        caption="Scoring. Line clears caused by a Life generation score exactly like normal ones.",
    ))

    story.append(h2("2.2  A living stack"))
    story.append(P(
        "Every <b>N</b> piece locks (N = 8 at the start of a game), one Game of Life generation is "
        "applied to the visible board. Every filled cell counts as alive, whatever piece it came from. "
        "Counting the eight cells around each cell:"
    ))
    story.append(table(
        [
            ["Cell", "Filled neighbours", "Result"],
            ["Block", "2 or 3", "Survives and keeps its colour"],
            ["Block", "0, 1, or 4 or more", "Dies and leaves a hole"],
            ["Empty cell", "exactly 3", "A grey garbage block is born"],
        ],
        [3.2 * cm, 4.6 * cm, FRAME_W - 7.8 * cm],
        caption="The Life rule as applied to the stack (Conway’s B3/S23).",
    ))
    story.append(P("Four refinements make the rule playable:"))
    story += bullets([
        "<b>Only the surface evolves.</b> In each column only the topmost block and the open air above "
        "it can change. Deeper blocks are frozen, although they still count as neighbours.",
        "<b>Edges are dead.</b> The walls and the floor count as empty cells; the hidden spawn rows are "
        "never changed and do not count as neighbours.",
        "<b>The falling piece is protected.</b> It does not count as a neighbour, and nothing is ever "
        "born on top of it.",
        "<b>Floating blocks settle.</b> After the generation, each group of edge-connected blocks falls "
        "as one rigid chunk until it lands. Any rows completed by the generation then clear and score "
        "like normal line clears.",
    ])
    story.append(figure(
        "life.png",
        "One generation computed by the game’s own code on an example stack. (a) The marks show what "
        "the rule will do: seven births along the surface and five deaths. (b) The board immediately "
        "after the rule. (c) The board after the floating groups have settled.",
    ))
    story.append(P(
        "The sidebar counts down the locks until the next generation, and pressing <b>G</b> shows a "
        "preview of it on the board: hollow squares mark cells that will be born and dark dots mark "
        "blocks that will die. Because the rule is deterministic, a player who reads the preview can "
        "place the last piece before a generation so that Life repairs the stack instead of damaging it."
    ))

    story.append(h2("2.3  Fertile zones"))
    story.append(P(
        "A second, hidden grid of numbers between 0 and 1 (the coupled map lattice, Section 4.2) "
        "evolves chaotically in the background, four times per second. A generation may only change "
        "cells whose value is above a <b>fertility threshold t</b> (0.5 at the start). The set of "
        "fertile cells is frozen at the start of the game and again right after each generation, so "
        "it stays fixed while the player plans for the next one. Pressing <b>C</b> tints the fertile "
        "cells, and the sidebar shows the fertile share of the board."
    ))

    story.append(h2("2.4  Adaptive difficulty and the director"))
    story.append(P(
        "At every level-up the game re-tunes the two knobs that control Life: <b>N</b>, the number of "
        "locks between generations (fewer is harder), and <b>t</b>, the fertility threshold (lower is "
        "harder because more cells are fertile). The decision is made in two stages, shown in "
        "Figure 2: a game-theoretic director picks the <i>kind</i> of Life, and a linear program "
        "picks <i>how much</i> of it, based on how high the player’s stack sat during the level."
    ))
    story.append(figure(
        "levelup.png",
        "What happens at a level-up. Steps 4 and 5 are the game-theory and linear-programming "
        "components described in Sections 4.5 and 4.4.",
    ))

    story.append(h2("2.5  Game over and controls"))
    story.append(P(
        "The game ends when a new piece cannot appear because its spawn position is blocked, when a "
        "piece locks entirely inside the hidden rows, or when a Life generation leaves the falling piece "
        "in a position where it no longer fits."
    ))
    story.append(table(
        [
            ["Key", "Action", "Key", "Action"],
            ["← / →", "Move (auto-repeat after 0.17 s, then every 0.05 s)", "G", "Toggle the generation preview"],
            ["↓", "Soft drop", "C", "Toggle the fertile-cell tint"],
            ["↑ or X / Z", "Rotate clockwise / counter-clockwise", "P / R", "Pause / restart"],
            ["Space", "Hard drop", "Esc", "Quit"],
        ],
        [2.2 * cm, 6.6 * cm, 1.4 * cm, FRAME_W - 10.2 * cm],
        caption="Controls.",
    ))

    # ------------------------------------------------------------- 3 architecture
    story.append(CondPageBreak(9 * cm))
    story.append(h1("3  System architecture"))
    story.append(P(
        "Evoltris is written in Python. The simulation is separated from presentation: the Tetris, "
        "Life and CML engines are pure NumPy code with no graphics dependency, which lets the whole "
        "game run headlessly for testing and for the bot experiments in Section 5. A single "
        "<font name='Mono'>World</font> object owns every engine and advances each on its own fixed "
        "timestep (1/120 s for the game, 0.25 s for the CML), independent of the display frame rate."
    ))
    story.append(figure(
        "architecture.png",
        "Data flow between the components. The engines never reference each other; every interaction "
        "goes through the board–Life coupling or through the World at level-ups.",
    ))
    story.append(P(
        "The engines interact only through a <i>coupling</i> object with three hooks: after a piece "
        "locks, after a Life step and after a CML step. The board–Life coupling counts locks, takes the "
        "fertility snapshot, applies generations and hands the evolved board back to the Tetris engine, "
        "which clears and scores any full rows. Every tunable constant lives in one configuration "
        "module as immutable data classes, and 145 automated tests cover the engines, the coupling, "
        "the optimizers and the renderer."
    ))

    # ------------------------------------------------------------- 4 maths
    story.append(CondPageBreak(12 * cm))
    story.append(h1("4  Mathematical concepts and how the game uses them"))
    story.append(P(
        "Each subsection starts with a short, self-contained overview of the concept and then explains "
        "how Evoltris uses it, with the exact formulas and parameters from the implementation."
    ))

    # 4.1 Life
    story.append(h2("4.1  Cellular automata and Conway’s Game of Life"))
    story.append(h3("Overview"))
    story.append(P(
        "A <i>cellular automaton</i> is a grid of cells, each in one of a finite set of states, that "
        "evolves in discrete time steps. At each step every cell updates simultaneously according to a "
        "fixed rule that looks only at the cell and its neighbours. Despite their simplicity, cellular "
        "automata can produce strikingly complex behaviour."
    ))
    story.append(P(
        "John Conway’s <b>Game of Life</b> (popularised by Gardner in 1970) is the best-known example. "
        "Cells are dead or alive, and each cell looks at its <i>Moore neighbourhood</i>, the eight "
        "cells that touch it horizontally, vertically or diagonally. Writing <i>a</i> ∈ {0, 1} for a "
        "cell’s state and <i>n</i> for the number of live neighbours, the next state is"
    ))
    story.append(eq("<i>a</i>′ = [ <i>n</i> = 3 ]  ∨  ( <i>a</i> = 1  ∧  <i>n</i> = 2 )"))
    story.append(P(
        "In words: a dead cell with exactly three live neighbours is born (B3), and a live cell with two "
        "or three live neighbours survives (S23); every other cell is dead in the next generation. The "
        "rule produces <i>still lifes</i> that never change (a 2×2 block), <i>oscillators</i> that "
        "repeat (the three-cell “blinker” flips between horizontal and vertical every step), and "
        "<i>gliders</i> that travel across the grid. Life is even Turing-complete: patterns can "
        "be built that perform any computation (Berlekamp, Conway and Guy, 1982). A finite grid also "
        "needs a <i>boundary condition</i> that says what lies beyond the edge: dead cells (fixed), "
        "the opposite edge (periodic), or a mirror of the edge cell (reflective)."
    ))
    story.append(h3("How Evoltris uses it"))
    story.append(P(
        "The Tetris board is the Life grid. Let <i>A</i> be the binary matrix with <i>A</i><sub>ij</sub> "
        "= 1 where the visible board is filled. Neighbour counts are computed for the whole board at "
        "once by padding <i>A</i> with one ring of dead cells (the fixed boundary, so walls and floor "
        "are dead) and adding the eight shifted copies of the padded array:"
    ))
    story.append(eq(
        "<i>n</i><sub>ij</sub> = Σ<sub>(dy, dx) ≠ (0, 0)</sub> <i>A</i><sub>i+dy, j+dx</sub>,     "
        "<i>A</i>′ = (<i>n</i> = 3)  ∨  (<i>A</i>  ∧  <i>n</i> = 2)"
    ))
    story.append(P(
        "This is a handful of vectorised array operations, so a full generation costs well under a "
        "millisecond. Several restrictions turn the raw rule into a game mechanic:"
    ))
    story += bullets([
        "<b>Surface mask.</b> With <i>top</i>(<i>j</i>) the row of the highest block in column "
        "<i>j</i> and depth <i>K</i> = 1, a cell may change only if its row is above "
        "<i>top</i>(<i>j</i>) + <i>K</i>. Cells outside the mask keep their state but still contribute "
        "to their neighbours’ counts.",
        "<b>Fertility mask.</b> Cells whose frozen CML value is not above the threshold are excluded "
        "too (Section 4.2). The final update is <i>A</i>′ where the cell is changeable and <i>A</i> "
        "elsewhere.",
        "<b>Identity of cells.</b> Surviving blocks keep their piece colour; births become a distinct "
        "garbage value; births on the falling piece’s cells are suppressed.",
        "<b>Settling.</b> The evolved board is decomposed into 4-connected components (groups of "
        "blocks joined along edges), found by a flood fill. Components are dropped one row at a time "
        "as rigid bodies, lowest first, and the process repeats until nothing moves, so components "
        "that land on each other fall together.",
    ])
    story.append(P(
        "Each refinement was justified by measurement. Without settling, dead blocks leave covered holes "
        "and every game is lost within a few dozen pieces (24 of 24 games, at 0.01–0.02 lines per piece). "
        "Letting every column collapse straight down makes Life a harmless eroder (0 of 24 losses). "
        "Surface-only evolution with rigid cluster settling is the setting in which ignoring Life is "
        "punished and planning for it is rewarded (Table 6)."
    ))

    # 4.2 CML
    story.append(h2("4.2  Chaos: the logistic map and coupled map lattices"))
    story.append(h3("Overview"))
    story.append(P(
        "The <b>logistic map</b> <i>f</i>(<i>x</i>) = <i>r</i> <i>x</i> (1 − <i>x</i>) is the "
        "standard example of how a simple deterministic rule can behave unpredictably (May, 1976). "
        "For 0 ≤ <i>r</i> ≤ 4 it maps [0, 1] into itself. Iterating "
        "<i>x</i><sub>k+1</sub> = <i>f</i>(<i>x</i><sub>k</sub>): for small <i>r</i> the orbit "
        "settles to a fixed point; above <i>r</i> = 3 it alternates between two values, then four, "
        "eight and so on in a <i>period-doubling cascade</i> whose spacing shrinks by Feigenbaum’s "
        "constant (≈ 4.669). Beyond <i>r</i> ≈ 3.5699 the behaviour becomes <i>chaotic</i> for most "
        "<i>r</i>: orbits never repeat, and two starting values that differ by a tiny amount separate "
        "exponentially fast (sensitive dependence on initial conditions)."
    ))
    story.append(P(
        "A <b>coupled map lattice</b> (CML), introduced by Kaneko in the 1980s, places one such map on "
        "every site of a grid and lets neighbouring sites influence each other. With diffusive coupling "
        "of strength ε over the four orthogonal (von Neumann) neighbours, every site updates as"
    ))
    story.append(eq(
        "<i>x</i>′<sub>ij</sub> = (1 − ε) <i>f</i>(<i>x</i><sub>ij</sub>) + (ε / 4) "
        "Σ<sub>4 neighbours</sub> <i>f</i>(<i>x</i><sub>nbr</sub>)"
    ))
    story.append(P(
        "Each new value is a convex combination of values in [0, 1], so the lattice provably stays in "
        "[0, 1] for any 0 ≤ ε ≤ 1. Coupling smooths the field into patches while the local map keeps "
        "it chaotic, so a CML generates spatiotemporal patterns: structured enough to show regions, "
        "irregular enough never to settle. With periodic or reflective (zero-flux) boundaries the "
        "coupling also conserves the total Σ <i>f</i>(<i>x</i>)."
    ))
    story.append(h3("How Evoltris uses it"))
    story.append(P(
        "Evoltris runs a CML on a lattice the same size as the board (22 × 10), with <i>r</i> = 3.9 "
        "(chaotic regime), ε = 0.3, reflective boundaries and one update every 0.25 s. The CML never "
        "sets cells alive or dead; it acts as an environmental <b>fertility mask</b>: a Life "
        "generation may only change cell (<i>i</i>, <i>j</i>) if <i>x</i><sub>ij</sub> &gt; <i>t</i>. "
        "Combined with the surface mask, the frozen set is"
    ))
    story.append(eq(
        "<i>frozen</i> = ¬<i>surface</i>  ∨  ¬[ <i>x</i> &gt; <i>t</i> ],     "
        "<i>A</i>′ = <i>A</i> on <i>frozen</i> cells"
    ))
    story.append(P(
        "An important design decision followed from measuring the lattice. At these parameters the "
        "field is close to a period-2 oscillation: after one step only about 25% of cells keep the same "
        "fertile/infertile state, and after two steps about 80% do (Figure 4). A mask read at the moment "
        "of the generation would therefore be effectively random from the player’s point of view. "
        "Evoltris instead takes a <b>snapshot</b> of the mask at the start of the game and right after "
        "each generation, and holds it fixed until the next one. The player gets the whole interval "
        "between generations to plan around a stable mask, the G preview stays exact, and every "
        "generation still faces a fresh, chaotic mask."
    ))
    story.append(figure(
        "cml.png",
        "The CML fertility mask (dark = fertile, CML value above 0.5) at two consecutive steps, and the "
        "share of cells whose mask matches step k as time goes on. The alternation shows why the game "
        "snapshots the mask instead of reading it live.",
    ))
    story.append(P(
        "The threshold <i>t</i> is the handle the optimizers use: a lower threshold makes more of the "
        "board fertile (roughly half to two-thirds of cells at <i>t</i> = 0.5), so Life acts on more "
        "cells and the game is harder."
    ))

    # 4.3 regression
    story.append(h2("4.3  Least-squares regression"))
    story.append(h3("Overview"))
    story.append(P(
        "Linear regression models a measured quantity <i>y</i> as a linear function of inputs, "
        "<i>y</i> ≈ β<sub>0</sub> + β<sub>1</sub><i>x</i><sub>1</sub> + β<sub>2</sub><i>x</i><sub>2</sub>. "
        "Given observations stacked as a design matrix <i>X</i> (one row per observation, with a "
        "leading column of ones) and a vector <i>y</i>, the least-squares coefficients minimise the "
        "sum of squared residuals ‖<i>y</i> − <i>X</i>β‖², and satisfy the normal equations"
    ))
    story.append(eq("<i>X</i><super>T</super><i>X</i> β = <i>X</i><super>T</super><i>y</i>"))
    story.append(P(
        "The coefficient of determination <i>R</i>² = 1 − SS<sub>res</sub> / SS<sub>tot</sub> "
        "measures the share of the variation in <i>y</i> that the model explains (1 is a perfect fit)."
    ))
    story.append(h3("How Evoltris uses it"))
    story.append(P(
        "A linear program needs linear relationships between its decisions and their effects. These "
        "were measured: the planning bot played 24 seeded games at each point of a 5 × 5 grid, with "
        "<i>N</i> ∈ {4, 6, 8, 10, 12} and <i>t</i> ∈ {0.3, 0.4, 0.5, 0.6, 0.7} (600 games in total). "
        "Fitting the mean stack height and the loss rate gave"
    ))
    story.append(eq(
        "height(<i>N</i>, <i>t</i>) = 10.27 − 0.2205 <i>N</i> − 1.813 <i>t</i>     (rows, "
        "<i>R</i>² = 0.83)"
    ))
    story.append(eq(
        "loss(<i>N</i>, <i>t</i>) = 0.955 − 0.0538 <i>N</i> − 0.300 <i>t</i>     (share of games lost, "
        "<i>R</i>² = 0.83)"
    ))
    story.append(P(
        "Both knobs act in the expected direction. Each additional lock between generations lowers the "
        "predicted stack by 0.22 rows and the loss rate by 5.4 percentage points; raising <i>t</i> "
        "across its whole range (0.3 to 0.7) lowers the stack by 0.73 rows and the loss rate by 12 "
        "points. The coefficients are stored in the configuration, and a script refits them whenever "
        "the mechanics change."
    ))

    # 4.4 LP
    story.append(h2("4.4  Linear programming"))
    story.append(h3("Overview"))
    story.append(P(
        "A <b>linear program</b> (LP) chooses values for decision variables to minimise or maximise a "
        "linear objective subject to linear constraints. In standard form:"
    ))
    story.append(eq(
        "minimise  <i>c</i><super>T</super><i>x</i>   subject to   <i>A</i><sub>ub</sub><i>x</i> ≤ "
        "<i>b</i><sub>ub</sub>,   <i>A</i><sub>eq</sub><i>x</i> = <i>b</i><sub>eq</sub>,   "
        "<i>l</i> ≤ <i>x</i> ≤ <i>u</i>"
    ))
    story.append(P(
        "The constraints carve out a convex polytope, the <i>feasible region</i>. If an optimum exists, "
        "one is attained at a vertex of that polytope, which is the insight behind Dantzig’s "
        "<b>simplex method</b> (1947): walk from vertex to adjacent vertex, always improving the "
        "objective. Modern solvers combine simplex and interior-point methods; Evoltris uses SciPy’s "
        "interface to <b>HiGHS</b>, a high-performance open-source solver (Huangfu and Hall, 2018). Two "
        "standard modelling techniques appear below. An absolute value |<i>e</i>| in an objective is "
        "linearised with an auxiliary variable <i>s</i> and the pair of constraints <i>e</i> ≤ <i>s</i>, "
        "−<i>e</i> ≤ <i>s</i>. And when a variable must be an integer, the LP <i>relaxation</i> (the "
        "same problem without the integrality requirement) can be solved first and the variable then "
        "branched on its floor and ceiling; this is the first step of branch-and-bound."
    ))
    story.append(h3("How Evoltris uses it"))
    story.append(P(
        "At each level-up the game must choose <i>N</i> (an integer from 4 to 12) and <i>t</i> (from "
        "0.3 to 0.7). It first updates a <b>target difficulty</b> <i>H</i>*, measured in predicted "
        "stack rows, from the player’s mean stack height <i>h</i> over the level just played:"
    ))
    story.append(eq("<i>H</i>* ← <i>H</i>* + 0.5 · (7 − <i>h</i>)"))
    story.append(P(
        "A player whose stack stayed below the comfortable height of 7 rows is coping well, so the "
        "target rises; a player stacking higher gets an easier target. This is a proportional "
        "controller with gain 0.5. The game then solves"
    ))
    story.append(code([
        "minimise    s",
        "subject to  height(N, t) − s ≤ H*",
        "           −height(N, t) − s ≤ −H*         (together: s ≥ |height(N, t) − H*|)",
        "            loss(N, t)       ≤ 0.5         (fairness limit)",
        "            4 ≤ N ≤ 12,   0.3 ≤ t ≤ 0.7,   s ≥ 0",
    ]))
    story.append(P(
        "The optimum is the setting whose predicted difficulty is closest to the target among the "
        "settings the planning bot is predicted to survive at least half the time. Because <i>N</i> "
        "must be an integer, the relaxation is solved first; the problem is then re-solved with "
        "<i>N</i> fixed to the floor and to the ceiling of the relaxed value, and the better feasible "
        "answer is kept. The bounds on <i>N</i> are integers and the loss falls as <i>N</i> rises, so "
        "rounding toward the easier side always remains feasible."
    ))
    story.append(figure(
        "lpp.png",
        "The LP’s decision space. The blue line is where predicted loss equals the 50% fairness "
        "limit; settings to its right are allowed. Contours show predicted stack height, so the LP "
        "effectively slides along them to find the target difficulty.",
    ))
    story.append(P(
        "Two further LPs, solved once at the start, find the lowest and highest predicted heights the "
        "fair region can reach (6.35 and 8.23 rows). The target is clamped to that range. Without the "
        "clamp, a strong player’s target kept climbing past anything the fairness limit allowed, and a "
        "subsequent run of bad levels took several level-ups to have any effect (integral windup); a "
        "regression test now checks that one bad level eases the game immediately. Feasibility of a "
        "box-constrained problem with a single linear loss constraint is checked cheaply: a linear "
        "function attains its minimum over a box at a corner, so the problem is feasible exactly when "
        "the easiest corner meets the limit."
    ))
    story.append(callout(
        "Choosing the fairness limit.",
        "The limit was chosen from a sweep (Table 8). It hardly changes how a planning bot fares, "
        "because the adaptive target holds its stack near 7.5 rows at every limit, but it sets how "
        "costly ignoring Life is and how far settings can swing between levels. At 50% the game uses "
        "the widest range of settings a planning player still survives.",
    ))

    # 4.5 game theory
    story.append(h2("4.5  Game theory: zero-sum games and Nash equilibrium"))
    story.append(h3("Overview"))
    story.append(P(
        "A finite <b>two-player zero-sum game</b> is described by a payoff matrix <i>A</i>: the row "
        "player chooses row <i>i</i>, the column player chooses column <i>j</i>, and the row player "
        "receives <i>A</i><sub>ij</sub>, which the column player loses. A <i>pure</i> strategy picks "
        "one row or column; a <i>mixed</i> strategy is a probability distribution over them. A pair "
        "of strategies is a <b>Nash equilibrium</b> (Nash, 1950) when neither player can gain by "
        "changing their own strategy alone."
    ))
    story.append(P(
        "Von Neumann’s <b>minimax theorem</b> (1928) states that every finite zero-sum game has an "
        "equilibrium in mixed strategies, and that the row player’s best guaranteed payoff equals the "
        "column player’s best guaranteed limit: max<sub>x</sub> min<sub>y</sub> <i>x</i><super>T</super>"
        "<i>A</i><i>y</i> = min<sub>y</sub> max<sub>x</sub> <i>x</i><super>T</super><i>A</i><i>y</i> = "
        "<i>v</i>, the <i>value</i> of the game. If some entry is simultaneously the smallest in its "
        "row and the largest in its column, it is a <i>saddle point</i> and both players have pure "
        "optimal strategies. Equilibria of zero-sum games are computed exactly by linear programming: "
        "the column player’s optimal mix <i>y</i> solves"
    ))
    story.append(eq(
        "minimise <i>v</i>   subject to   Σ<sub>j</sub> <i>A</i><sub>ij</sub> <i>y</i><sub>j</sub> "
        "≤ <i>v</i>  for every row <i>i</i>,   Σ<sub>j</sub> <i>y</i><sub>j</sub> = 1,   <i>y</i> ≥ 0"
    ))
    story.append(P(
        "and the row player’s mix solves the dual LP; LP duality is exactly the minimax theorem."
    ))
    story.append(h3("How Evoltris uses it"))
    story.append(P(
        "The LP decides <i>how hard</i> a level is, but many (<i>N</i>, <i>t</i>) pairs share the same "
        "predicted difficulty, for example Life that comes often but touches few cells, or rarely but "
        "touches many. Evoltris lets a <b>director</b> choose among these as a zero-sum game against the "
        "player:"
    ))
    story += bullets([
        "<b>Director’s strategies</b> are three styles of Life: <i>rare &amp; wide</i> (<i>t</i> = 0.3), "
        "<i>balanced</i> (<i>t</i> = 0.5) and <i>frequent &amp; narrow</i> (<i>t</i> = 0.7). For each, "
        "the LP sets <i>N</i> so the predicted difficulty is the same; at the default difficulty "
        "this gives <i>N</i> = 10, 8 and 6.",
        "<b>Player’s strategies</b> are four play styles, implemented as bot policies: <i>naive</i> "
        "(ignores Life), <i>aware</i> (plans on the lock that triggers a generation), <i>cautious</i> "
        "(also weighs a hypothetical generation on every other lock) and <i>well</i> (keeps a column "
        "open for four-line clears).",
        "<b>Payoff</b> is the player’s survival rate, measured over 48 seeded games for each of the 12 "
        "pairs. The player maximises it and the director minimises it.",
    ])
    story.append(table(
        [
            ["Player style \\ Director style", "rare & wide", "balanced", "frequent & narrow"],
            ["naive", "0.250", "0.146", "0.146"],
            ["aware", "0.792", "0.646", "0.604  (equilibrium)"],
            ["cautious", "0.000", "0.000", "0.042"],
            ["well", "0.146", "0.104", "0.062"],
        ],
        [5.0 * cm, 3.1 * cm, 3.1 * cm, FRAME_W - 11.2 * cm],
        caption="Measured payoff matrix (survival rate). With 48 games per cell, differences below "
                "about 0.07 are within noise.",
        bold_rows=(2,),
    ))
    story.append(P(
        "Solving the LP gives a <b>pure</b> equilibrium with value <i>v</i> = 0.604: <i>aware</i> is "
        "the best play style against every kind of Life, and against it <i>frequent &amp; narrow</i> "
        "is the hardest, so the entry 0.604 is a saddle point. The director therefore always plays "
        "frequent &amp; narrow. This captures a genuine effect that the LP’s height model misses: at "
        "equal predicted stack height, frequent and narrow Life is much harder to survive than rare and "
        "wide Life (0.60 against 0.79 for the planning bot)."
    ))
    story.append(P(
        "In the running game the director samples its style from the equilibrium mix at each "
        "level-up, and the LP then optimises <i>N</i> with <i>t</i> fixed to that style. If no "
        "<i>N</i> is fair at the chosen <i>t</i>, the director is overruled and <i>t</i> is freed. With "
        "<i>t</i> = 0.7 the LP may go as low as <i>N</i> = 5. The equilibrium would become genuinely "
        "mixed, and the director would randomise, only if different play styles were each best against "
        "a different kind of Life; with the current bots no such trade-off exists."
    ))

    # 4.6 other
    story.append(h2("4.6  Further mathematics in the engine"))
    story += bullets([
        "<b>Sampling without replacement (7-bag).</b> Each bag is a uniformly random permutation of "
        "the seven pieces. Every shape appears with frequency exactly 1/7, and at most 12 other pieces "
        "can separate two pieces of the same shape (first in one bag, last in the next).",
        "<b>Rotations.</b> SRS rotation states are generated by rotating the spawn shape by 90° "
        "inside its bounding box, (<i>r</i>, <i>c</i>) ↦ (<i>c</i>, <i>s</i> − 1 − <i>r</i>) for box "
        "size <i>s</i>. The published kick tables use an upward <i>y</i>-axis and are converted to the "
        "board’s downward rows.",
        "<b>Geometric gravity curve.</b> The fall interval is 0.8 · 0.85<super>level</super> seconds, "
        "with a floor of 0.05 s, reached at level 18.",
        "<b>Fixed-timestep integration.</b> Frame time is accumulated and consumed in exact 1/120 s "
        "steps, with separate accumulators for the CML. The simulation is deterministic and "
        "independent of frame rate; with seeds fixed, every experiment in this report is exactly "
        "reproducible.",
    ])

    # ------------------------------------------------------------- 5 evaluation
    story.append(CondPageBreak(12 * cm))
    story.append(h1("5  Evaluation"))
    story.append(h2("5.1  Method"))
    story.append(P(
        "Balance was measured with heuristic bots rather than human players. For each candidate "
        "placement a bot scores the resulting board by aggregate column height, holes, bumpiness and "
        "lines cleared (a standard Tetris evaluation), then places the best piece directly. The "
        "<i>naive</i> bot scores the board as placed; the <i>aware</i> bot, on the lock that triggers a "
        "generation, scores the board that generation would produce. Each setting was played with "
        "fixed seeds (24 games, or 48 for the payoff matrix), capped at 500 pieces, with four CML steps "
        "per piece (about one second of play). With 24 games, differences of two or three losses are "
        "within noise."
    ))
    story.append(h2("5.2  Results"))
    story.append(table(
        [
            ["Setting (fertility mask off)", "Naive: losses · lines/piece", "Aware: losses · lines/piece"],
            ["No Life", "2/24 · 0.39", "2/24 · 0.39"],
            ["Whole board, no settling, N = 5", "24/24 · 0.02", "24/24 · 0.01"],
            ["Whole board, column settling, N = 5", "0/24 · 0.24", "0/24 · 0.19"],
            ["Surface, cluster settling, N = 8 (default)", "20/24 · 0.31", "8/24 · 0.34"],
            ["Surface, cluster settling, N = 5", "24/24 · 0.27", "9/24 · 0.31"],
            ["Surface, cluster settling, N = 12", "19/24 · 0.33", "2/24 · 0.36"],
        ],
        [6.6 * cm, 4.6 * cm, FRAME_W - 11.2 * cm],
        caption="Coupling design. Only surface evolution with cluster settling separates players who "
                "plan for Life from those who do not; N then acts as a smooth difficulty knob.",
        bold_rows=(4,),
    ))
    story.append(table(
        [
            ["Default coupling, N = 8 at the start", "Naive: losses · lines/piece", "Aware: losses · lines/piece"],
            ["Fertility mask off", "20/24 · 0.31", "8/24 · 0.34"],
            ["Fertility mask on (t = 0.5)", "20/24 · 0.33", "12/24 · 0.34"],
            ["Mask + adaptive LP (50% limit)", "16/24 · 0.34", "5/24 · 0.34"],
            ["Mask + adaptive LP + director (shipped)", "14/24 · 0.35", "7/24 · 0.34"],
        ],
        [6.6 * cm, 4.6 * cm, FRAME_W - 11.2 * cm],
        caption="Adding each system. With the director, the planning bot’s mean stack rises from 7.5 "
                "to 8.5 rows: frequent and narrow Life is measurably harder.",
        bold_rows=(4,),
    ))
    story.append(table(
        [
            ["Fairness limit", "N range used", "Largest one-level N jump", "Naive losses", "Aware losses"],
            ["15%", "12", "0", "9/24", "5/24"],
            ["25%", "11–12", "1", "16/24", "7/24"],
            ["35%", "9–12", "3", "13/24", "6/24"],
            ["50% (shipped)", "7–12", "5", "16/24", "5/24"],
            ["≥ 65% (no limit)", "4–12", "8", "21/24", "7/24"],
        ],
        [3.4 * cm, 2.9 * cm, 3.9 * cm, 2.9 * cm, FRAME_W - 13.1 * cm],
        caption="Effect of the LP’s fairness limit (measured with the adaptive LP before the director "
                "was added, so t was free).",
        bold_rows=(4,),
    ))
    story.append(h2("5.3  Findings"))
    story += bullets([
        "<b>Strategy matters.</b> Across every configuration that keeps Life meaningful, the bot that "
        "plans for the next generation loses far fewer games than the one that ignores it.",
        "<b>The adaptation works as a controller.</b> With the LP enabled, the planning bot’s outcome "
        "is roughly independent of the fairness limit (5–7 losses in 24); the limit instead sets "
        "how harsh the game is on unplanned play and how far the settings swing.",
        "<b>The CML threshold is a real but secondary knob.</b> Its effect on stack height (0.73 rows "
        "across its range) is smaller than that of <i>N</i> (1.76 rows from 4 to 12), but it changes the "
        "character of Life, which the director exploits.",
    ])

    # ------------------------------------------------------------- 6 limitations
    story.append(h1("6  Limitations and future work"))
    story += bullets([
        "<b>Bot-based tuning.</b> Every model and payoff describes heuristic bots. Skilled humans "
        "probably cope better than the planning bot, so the game may feel easier than the numbers "
        "suggest. Logging stack heights from real sessions and refitting is the natural next step.",
        "<b>A pure equilibrium.</b> The director never randomises because one play style dominates. "
        "Adding player styles with genuine trade-offs, such as a planner tuned for frequent "
        "generations against one tuned for rare ones, would test whether a mixed equilibrium exists.",
        "<b>Coarse adaptation.</b> Settings change only at level-ups (every 10 lines); level 0 always "
        "uses N = 8, t = 0.5; and the narrow fair range makes the controller tend to jump between its "
        "extremes rather than move gradually.",
        "<b>Linear models.</b> The fits explain 83% of the variance; the rest is noise and "
        "non-linearity, and predictions far outside the measured grid are extrapolations.",
        "<b>Presentation.</b> The game has no hold piece, menus, sound or persistent high scores.",
    ])

    story.append(h1("7  Conclusion"))
    story.append(P(
        "Evoltris turns four mathematical ideas into one coherent mechanic. Conway’s Game of Life makes "
        "the stack a dynamical system; a chaotic coupled map lattice decides where that system may act, "
        "made playable by snapshotting it; a least-squares model and a linear program re-tune the "
        "system at every level to the player’s observed comfort while enforcing a fairness constraint; "
        "and a zero-sum game, also solved by linear programming, chooses which kind of Life to present. "
        "The measurements show that the result rewards planning, adapts its difficulty, and surfaces "
        "effects, such as frequent-and-narrow Life being harder at equal predicted difficulty, that no "
        "single component would reveal on its own."
    ))

    # ------------------------------------------------------------- appendices
    story.append(PageBreak())
    story.append(h1("Appendix A  Configuration reference"))
    story.append(table(
        [
            ["Parameter", "Default", "Meaning"],
            ["coupling.locks_per_generation", "8", "N at the start: locks between Life generations"],
            ["coupling.surface_depth", "1", "Rows below each column’s top that may evolve"],
            ["coupling.settle", "clusters", "Rigid settling of 4-connected groups"],
            ["coupling.fertility_threshold", "0.5", "t at the start: CML value needed to be fertile"],
            ["cml.r / cml.coupling", "3.9 / 0.3", "Logistic parameter and coupling strength ε"],
            ["cml.boundary / step_interval", "reflective / 0.25 s", "CML edge rule and update period"],
            ["adaptive.n_bounds / t_bounds", "4–12 / 0.3–0.7", "Ranges the LP may choose from"],
            ["adaptive.max_aware_loss", "0.5", "Fairness limit on predicted loss"],
            ["adaptive.comfort_height / gain", "7 rows / 0.5", "Target controller parameters"],
            ["strategy.styles", "t = 0.3, 0.5, 0.7", "Director’s styles of Life"],
            ["tetris.lines_per_level", "10", "Lines per level (and per re-tune)"],
            ["tetris gravity", "0.8 s × 0.85^level", "Fall interval, floor 0.05 s"],
            ["tetris.lock_delay / max_lock_resets", "0.5 s / 15", "Lock timer and reset cap"],
        ],
        [5.6 * cm, 3.4 * cm, FRAME_W - 9.0 * cm],
    ))
    story.append(h1("Appendix B  Reproducing the results"))
    story.append(P("Every number in this report can be regenerated from the repository:"))
    story.append(code([
        "uv run evoltris                                          # play",
        "uv run pytest                                            # 145 tests",
        "uv run python scripts/balance_sweep.py --table coupling  # Table 6",
        "uv run python scripts/balance_sweep.py --table fertility # Table 7, rows 1-2",
        "uv run python scripts/balance_sweep.py --table fertility --adaptive   # Table 7, last row",
        "uv run python scripts/fit_difficulty.py --games 24       # Section 4.3 models",
        "uv run python scripts/fit_strategy.py --games 48         # Table 5 and its equilibrium",
    ]))
    story.append(P(
        "Two sets of numbers were measured before the director existed and cannot be rerun "
        "unchanged, because <font name='Mono'>--adaptive</font> now includes the director: the third "
        "row of Table 7 (adaptive LP alone) and Table 8 (fairness limits). Both used the same bots, "
        "seeds and piece cap."
    ))

    story.append(h1("References"))
    refs = [
        "Berlekamp, E. R., Conway, J. H., and Guy, R. K. (1982). <i>Winning Ways for your "
        "Mathematical Plays</i>, vol. 2. Academic Press.",
        "Dantzig, G. B. (1963). <i>Linear Programming and Extensions</i>. Princeton University Press.",
        "Feigenbaum, M. J. (1978). Quantitative universality for a class of nonlinear "
        "transformations. <i>Journal of Statistical Physics</i>, 19, 25–52.",
        "Gardner, M. (1970). Mathematical Games: The fantastic combinations of John Conway’s new "
        "solitaire game “life”. <i>Scientific American</i>, 223(4), 120–123.",
        "Huangfu, Q., and Hall, J. A. J. (2018). Parallelizing the dual revised simplex method. "
        "<i>Mathematical Programming Computation</i>, 10(1), 119–142.",
        "Kaneko, K. (1992). Overview of coupled map lattices. <i>Chaos</i>, 2(3), 279–282.",
        "May, R. M. (1976). Simple mathematical models with very complicated dynamics. "
        "<i>Nature</i>, 261, 459–467.",
        "Nash, J. F. (1950). Equilibrium points in n-person games. <i>Proceedings of the National "
        "Academy of Sciences</i>, 36(1), 48–49.",
        "von Neumann, J. (1928). Zur Theorie der Gesellschaftsspiele. <i>Mathematische Annalen</i>, "
        "100, 295–320.",
    ]
    story += [P(r, "ref") for r in refs]

    doc = ReportDoc(
        str(OUT),
        title="Evoltris — Technical Report",
        author="Evoltris project",
        subject="How Evoltris works and the mathematics behind it",
        creator="ReportLab",
    )
    doc.multiBuild(story)


if __name__ == "__main__":
    build()
    print("wrote", OUT)
