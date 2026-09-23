#!/usr/bin/env python3
# usage: cd ~/projects/citebench && uv run --no-project --with matplotlib python publish/charts/make_reddit_table.py   (the headline table as one image for Reddit/X)
import os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
rows = {}
for l in open(os.path.join(ROOT, "results", "report_150.md")):
    if l.startswith("| ") and ":v" in l and " pp" not in l:
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        p = lambda s: float(s.rstrip("%"))
        rows[(c[0], c[1])] = dict(n=int(c[3]), cites=int(c[6]), fab=p(c[7]), misgr=p(c[11]), gold=p(c[14]))

GROUPS = [
  ("Model on its own", [
    ("gpt-6-astra", "bare", "GPT-6 Astra"),
    ("claude-opus-5-5", "bare", "Claude Opus 5.5"),
    ("claude-fable-5-1", "bare", "Claude Fable 5.1"),
    ("gemini-3.1-pro-or", "bare", "Gemini 3.1 Pro"),
    ("local-gemma", "bare", "Gemma 4 26B (local, free)"),
  ]),
  ("Same model + Syfert legal research tools (free MCP)", [
    ("local-gemma", "mcp", "Gemma 4 26B + Syfert"),
    ("claude-sonnet-5-or", "mcp", "Claude Sonnet 5 + Syfert"),
    ("claude-fable-5-1-cc", "mcp", "Claude Fable 5.1 + Syfert"),
    ("claude-opus-5-5-cc", "mcp", "Claude Opus 5.5 + Syfert"),
  ]),
]
HEAD = ["", "Questions", "Citations\nchecked", "Invented case\n(per 100 cites)", "Misquotes real case\n(per 100 cites)", "Found the\nright case"]
SURF, INK, INK2, LINE, TINT, TINT2, HDR = "#fcfcfb", "#0b0b0b", "#52514e", "#dddcd8", "#fbe9df", "#f3f2ef", "#0b0b0b"
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
nrows = sum(len(g[1]) for g in GROUPS) + len(GROUPS)
H = 3.3 + 0.62 * nrows
fig = plt.figure(figsize=(16, H), dpi=150, facecolor=SURF); ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off()
ax.set_xlim(0, 100); ax.set_ylim(0, 100)
fig.text(0.04, 1 - 0.35 / H, "Do AI models cite real law correctly?", fontsize=24, fontweight="bold", color=INK, va="top")
fig.text(0.04, 1 - 0.85 / H, "150 real legal propositions (Florida, federal, 10 other states); every citation in every answer checked against 10.7M opinions.", fontsize=13, color=INK2, va="top")
cols = [4, 38, 50, 62, 78, 94]  # x centers/anchors in % of width
top, rh = 100 * (1 - 1.35 / H), 100 * 0.62 / H
y = top
for i, h in enumerate(HEAD):
    ax.text(cols[i], y, h, ha="left" if i == 0 else "center", va="center", fontsize=13, color=INK2, fontweight="bold")
y -= rh * 0.9; ax.plot([3, 99], [y, y], color=INK, lw=1.2)
for gi, (gname, items) in enumerate(GROUPS):
    y -= rh * 0.85
    ax.text(cols[0], y, gname, ha="left", va="center", fontsize=13.5, fontweight="bold", color=INK)
    for k, arm, label in items:
        y -= rh; r = rows[(k, arm)]
        if gi == 1: ax.add_patch(plt.Rectangle((3, y - rh / 2), 96, rh, color=TINT, lw=0, zorder=0))
        vals = [label, f"{r['n']}", f"{r['cites']}", f"{r['fab']:.1f}", f"{r['misgr']:.1f}", f"{r['gold']:.0f}%"]
        for i, v in enumerate(vals):
            ax.text(cols[i] + (1.5 if i == 0 else 0), y, v, ha="left" if i == 0 else "center", va="center",
                    fontsize=15 if i else 14.5, color=INK, fontweight="bold" if i >= 3 else "normal", zorder=2)
        ax.plot([3, 99], [y - rh / 2, y - rh / 2], color=LINE, lw=0.6, zorder=1)
fig.text(0.04, 0.25 / H, "Lower is better for 'invented' and 'misquotes'; higher is better for 'found the right case'. Misquote = the opinion does not contain the quoted words, or the case name is wrong.\n"
         "Syfert rows: Sonnet via API (55 of 60 graded); Fable and Opus via Claude Code with only the Syfert tools attached. The few 'invented' cites in the Claude/GPT rows are real cases at a wrong page.\n"
         "Preliminary, Sept 22 2026. Grader hand-audited at ~90% precision. Harness, questions and raw results: github.com/Gwonk1/citebench  |  citebench by syfert.com (I run both the tool and the grader).",
         fontsize=10.5, color=INK2, va="bottom")
out = os.path.join(ROOT, "publish", "charts", "reddit_table.png"); fig.savefig(out, facecolor=SURF); print("wrote", out)
