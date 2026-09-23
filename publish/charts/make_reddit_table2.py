#!/usr/bin/env python3
# usage: cd ~/projects/citebench && uv run --no-project --with matplotlib python publish/charts/make_reddit_table2.py   (headline table image, paired rows per model, colour-coded cells)
import os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
rows = {}
for l in open(os.path.join(ROOT, "results", "report_150.md")):
    if l.startswith("| ") and ":v" in l and " pp" not in l:
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        p = lambda s: float(s.rstrip("%"))
        rows[(c[0], c[1])] = dict(n=int(c[3]), cites=int(c[6]), fab=p(c[7]), misgr=p(c[11]), gold=p(c[14]))

MODELS = [  # (display name, bare key, mcp key)
    ("GPT-6 Astra", "gpt-6-astra", None),
    ("Claude Opus 5.5", "claude-opus-5-5", "claude-opus-5-5-cc"),
    ("Claude Fable 5.1", "claude-fable-5-1", "claude-fable-5-1-cc"),
    ("Claude Sonnet 5", None, "claude-sonnet-5-or"),
    ("Gemini 3.1 Pro", "gemini-3.1-pro-or", None),
    ("Gemma 4 26B, local", "local-gemma", "local-gemma"),
]
GOOD, WARN, BAD = "#d9f0d9", "#fdebc2", "#f6d0d0"
def tint(kind, v):
    if kind == "fab":  return GOOD if v < 1 else WARN if v < 5 else BAD
    if kind == "mis":  return GOOD if v < 5 else WARN if v < 15 else BAD
    return GOOD if v >= 85 else WARN if v >= 60 else BAD

SURF, INK, INK2, LINE, BAND = "#fcfcfb", "#0b0b0b", "#52514e", "#dddcd8", "#f3f2ef"
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
lines = [(m, ("bare" if b else None), ("mcp" if t else None)) for m, b, t in MODELS]
nrows = sum((1 if b else 0) + (1 if t else 0) for _, b, t in MODELS)
H = 3.8 + 0.6 * nrows + 0.25 * len(MODELS)
fig = plt.figure(figsize=(16, H), dpi=150, facecolor=SURF); ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off(); ax.set_xlim(0, 100); ax.set_ylim(0, 100)
fig.text(0.04, 1 - 0.35 / H, "Do AI models cite real law correctly?", fontsize=24, fontweight="bold", color=INK, va="top")
fig.text(0.04, 1 - 0.85 / H, "150 real legal propositions (Florida, federal, 10 other states). Every citation in every answer checked against 10.7M opinions.", fontsize=13, color=INK2, va="top")
HEAD = ["", "Questions", "Citations\nchecked", "Invented case\n(per 100 cites)", "Misquotes a real case\n(per 100 cites)", "Found the\nright case"]
cols = [4, 40, 51, 63, 78, 93]
rh, gap = 100 * 0.6 / H, 100 * 0.25 / H
y = 100 * (1 - 1.35 / H)
for i, h in enumerate(HEAD):
    ax.text(cols[i], y, h, ha="left" if i == 0 else "center", va="center", fontsize=13, color=INK2, fontweight="bold")
y -= rh * 0.75; ax.plot([3, 99], [y, y], color=INK, lw=1.2)
for name, bkey, tkey in MODELS:
    y -= gap
    n_lines = (1 if bkey else 0) + (1 if tkey else 0)
    ax.add_patch(Rectangle((3, y - n_lines * rh), 96, n_lines * rh, color=BAND, lw=0, zorder=0))
    ax.text(cols[0] + 1, y - rh * 0.5, name, ha="left", va="center", fontsize=15, fontweight="bold", color=INK, zorder=2)
    first = True
    for key, arm, sub in ((bkey, "bare", "on its own"), (tkey, "mcp", "+ Syfert tools")):
        if not key: continue
        y -= rh; r = rows[(key, arm)]
        ax.text(cols[0] + 21, y + rh * 0.5, sub, ha="left", va="center", fontsize=13.5, color=INK2 if arm == "bare" else "#9a3a10", fontweight="normal" if arm == "bare" else "bold", zorder=2)
        vals = [(f"{r['n']}", None), (f"{r['cites']}", None), (f"{r['fab']:.1f}", tint("fab", r["fab"])), (f"{r['misgr']:.1f}", tint("mis", r["misgr"])), (f"{r['gold']:.0f}%", tint("gold", r["gold"]))]
        for i, (v, bg) in enumerate(vals, start=1):
            if bg: ax.add_patch(FancyBboxPatch((cols[i] - 5.2, y + rh * 0.12), 10.4, rh * 0.76, boxstyle="round,pad=0,rounding_size=0.6", color=bg, lw=0, zorder=1))
            ax.text(cols[i], y + rh * 0.5, v, ha="center", va="center", fontsize=15, color=INK, fontweight="bold" if bg else "normal", zorder=2)
        first = False
    ax.plot([3, 99], [y, y], color=LINE, lw=0.6, zorder=1)
# legend for colours
ly = y - gap * 1.6
for i, (c, t) in enumerate(((GOOD, "good"), (WARN, "middling"), (BAD, "poor"))):
    ax.add_patch(FancyBboxPatch((4 + i * 11, ly - 0.9), 2.2, 1.8, boxstyle="round,pad=0,rounding_size=0.4", color=c, lw=0)); ax.text(7 + i * 11, ly, t, va="center", fontsize=12, color=INK2)
fig.text(0.04, 0.25 / H, "Lower is better for 'invented' and 'misquotes'; higher is better for 'found the right case'. Misquote = the opinion does not contain the quoted words, or the case name is wrong.\n"
         "Sonnet via API (55 of 60 graded); Fable and Opus '+ Syfert' via Claude Code with only the Syfert tools attached. GPT-6 and Gemini were not run with the tools.\n"
         "The few 'invented' cites in the Claude/GPT rows are real cases cited at a wrong page, not made-up cases.\n"
         "Preliminary, Sept 22 2026. Grader hand-audited at ~90% precision. Harness, questions and raw results: github.com/Gwonk1/citebench  |  citebench by syfert.com (I run both the tool and the grader).",
         fontsize=10.5, color=INK2, va="bottom")
out = os.path.join(ROOT, "publish", "charts", "reddit_table.png"); fig.savefig(out, facecolor=SURF); print("wrote", out)
