#!/usr/bin/env python3
# usage: cd ~/projects/citebench && uv run --no-project --with matplotlib python publish/charts/make_reddit_chart.py   (one plain chart of the g6 headline table for Reddit/X)
import re, sys, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
rows = {}
for l in open(os.path.join(ROOT, "results", "report_150.md")):
    if l.startswith("| ") and ":v" in l and " pp" not in l:
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        p = lambda s: float(s.rstrip("%")) if s.endswith("%") else None
        rows[(c[0], c[1])] = dict(n=int(c[5]), cites=int(c[6]), fab=p(c[7]), misgr=p(c[11]), gold=p(c[14]))

ORDER = [  # (model key, arm, label, is_tool_row)
    ("local-gemma", "bare", "Gemma 4 26B (local, free)", False),
    ("gemini-3.1-pro-or", "bare", "Gemini 3.1 Pro", False),
    ("claude-fable-5-1", "bare", "Claude Fable 5.1", False),
    ("gpt-6-astra", "bare", "GPT-6 Astra", False),
    ("claude-opus-5-5", "bare", "Claude Opus 5.5", False),
    ("claude-opus-5-5-cc", "mcp", "Claude Opus 5.5 + Syfert tools", True),
    ("claude-fable-5-1-cc", "mcp", "Claude Fable 5.1 + Syfert tools", True),
    ("local-gemma", "mcp", "Gemma 4 26B + Syfert tools", True),
    ("claude-sonnet-5-or", "mcp", "Claude Sonnet 5 + Syfert tools", True),
]
data = []
for k, arm, label, tool in ORDER:
    r = rows[(k, arm)]
    data.append((label, tool, r["misgr"], r["gold"], r["n"], r["cites"], r["fab"]))
data.sort(key=lambda d: -d[2])

BLUE, ORANGE, SURF, INK, INK2, GRID = "#2a78d6", "#eb6834", "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e2"
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"], "font.size": 13})
fig, (ax0, ax1, ax2) = plt.subplots(1, 3, figsize=(18, 9), dpi=150, facecolor=SURF, gridspec_kw={"width_ratios": [1.3, 1, 1], "wspace": 0.07})
labels = [d[0] for d in data]; y = range(len(data))[::-1]
for ax, idx, title, xmax in ((ax0, 6, "Out of 100 citations, how many point\nto a case that does not exist?", 100),
                            (ax1, 2, "Out of 100 citations, how many misquote\nor misname a real case?", 100),
                            (ax2, 3, "Out of 100 questions, how often did it\nfind the right case?", 100)):
    ax.set_facecolor(SURF)
    vals = [d[idx] for d in data]; cols = [ORANGE if d[1] else BLUE for d in data]
    bars = ax.barh(list(y), vals, color=cols, height=0.62, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_width() + 1.2, b.get_y() + b.get_height() / 2, (f"{v:.1f}" if 0 < v < 1 else f"{v:.0f}"), va="center", ha="left", color=INK, fontsize=14, fontweight="bold")
    ax.set_xlim(0, xmax * 1.12); ax.set_yticks(list(y)); ax.set_yticklabels(labels if ax is ax0 else [""] * len(labels), fontsize=14, color=INK)
    ax.set_title(title, loc="left", fontsize=15, color=INK, pad=14)
    ax.grid(axis="x", color=GRID, zorder=0); ax.set_axisbelow(True)
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID); ax.tick_params(axis="x", colors=INK2, length=0); ax.tick_params(axis="y", length=0)
    ax.set_xticks([0, 25, 50, 75, 100])
ax2.legend(handles=[Patch(color=BLUE, label="Model on its own"), Patch(color=ORANGE, label="Same model + Syfert legal research tools (free MCP)")],
           loc="lower right", frameon=False, fontsize=13)
fig.suptitle("Do AI models cite real law correctly?   Left and middle: lower is better.   Right: higher is better.",
             x=0.04, ha="left", fontsize=19, fontweight="bold", color=INK, y=0.985)
ns = "; ".join(f"{d[0].split(' +')[0]}{' +tools' if d[1] else ''}: {d[4]} questions, {d[5]} citations" for d in data)
fig.text(0.04, 0.015, "Test: real legal propositions from U.S. cases (Florida, federal, and 10 other states), each model asked for the authority. Every citation checked against a 10.7M-opinion corpus.\n"
         "Same 150 questions for every bare row; tool rows 55 to 150 questions. A citation counts as misquoting if the opinion does not contain the quoted words or the case name is wrong.\n"
         "Preliminary, Sept 22 2026. Grader audited by hand at ~90% precision. Harness and data: github.com/Gwonk1/citebench  |  citebench by syfert.com",
         fontsize=10.5, color=INK2, va="bottom")
fig.subplots_adjust(left=0.21, right=0.985, top=0.85, bottom=0.13)
out = os.path.join(ROOT, "publish", "charts", "reddit_simple.png"); fig.savefig(out, facecolor=SURF); print("wrote", out)
