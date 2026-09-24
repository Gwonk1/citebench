#!/usr/bin/env python3
# usage: cd ~/projects/citebench && uv run --no-project --with matplotlib python publish/charts/make_reddit_table2.py   (headline table image: bare block, MCP v7 block + earlier-server sub-block, colour-coded cells)
import os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def read_report(fname):
    """{run_id: row} from a report.py markdown table; columns found by header name."""
    out, idx = {}, None
    for l in open(os.path.join(ROOT, "results", fname)):
        if not l.startswith("| "): continue
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        if c[0] == "model" and "fabricated_rate" in c:
            idx = {k: i for i, k in enumerate(c)}; continue
        if idx is None or len(c) != len(idx) or ":" not in c[2]: continue
        p = lambda k: float(c[idx[k]].rstrip("%"))
        out[c[2]] = dict(n=int(c[idx["graded"]]), cites=int(c[idx["cites"]]), fab=p("fabricated_rate"),
                         misgr=p("misgrounded_rate"), gold=p("gold_equiv"))
    return out
# Every row comes from the current report_150.md (grader g10), by run_id. Last column = gold_equiv
# (a cited opinion states the proposition verbatim, or gold_hit), not gold_recall.
rows = read_report("report_150.md")

BLOCKS = [  # (header, style, [(display name, small label, run_id)])
    ("On its own (no tools)", "main", [
        ("Claude Fable 5.1", "", "claude-fable-5-1:bare:v1"),
        ("Claude Opus 5.5", "", "claude-opus-5-5:bare:v1"),
        ("Claude Sonnet 5", "via Claude Code", "claude-sonnet-5-cc:bare:v7"),
        ("Gemini 3.1 Pro", "", "gemini-3.1-pro-or:bare:v1"),
        ("GPT-6 Astra", "", "gpt-6-astra:bare:v1"),
        ("Gemma 4 26B, local", "", "local-gemma:bare:v1"),
    ]),
    ("With Syfert MCP v7 (server upgraded 2026-09-23)", "main", [
        ("Claude Opus 5.5", "", "claude-opus-5-5-cc:mcp:v2"),
        ("Claude Sonnet 5", "via Claude Code", "claude-sonnet-5-cc:mcp:v7"),
        ("Gemma 4 26B, local", "", "local-gemma:mcp:v3"),
    ]),
    ("earlier server (v6, Sept 22)", "sub", [
        ("Claude Fable 5.1", "", "claude-fable-5-1-cc:mcp:v1"),
        ("Claude Opus 5.5", "", "claude-opus-5-5-cc:mcp:v1"),
        ("Claude Sonnet 5", "via API", "claude-sonnet-5-or:mcp:v1"),
        ("Gemma 4 26B, local", "", "local-gemma:mcp:v1"),
    ]),
]
for _, _, rs in BLOCKS:  # rank by the last column descending; ties by misquotes ascending
    rs.sort(key=lambda t: (-rows[t[2]]["gold"], rows[t[2]]["misgr"]))

GOOD, WARN, BAD = "#d9f0d9", "#fdebc2", "#f6d0d0"
def tint(kind, v):
    if kind == "fab":  return GOOD if v < 1 else WARN if v < 5 else BAD
    if kind == "mis":  return GOOD if v < 5 else WARN if v < 15 else BAD
    return GOOD if v >= 85 else WARN if v >= 60 else BAD

SURF, INK, INK2, LINE, BAND, HEADBG = "#fcfcfb", "#0b0b0b", "#52514e", "#dddcd8", "#f3f2ef", "#2b2a28"
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
nrows = sum(len(rs) for _, _, rs in BLOCKS)
nmain = sum(1 for _, s, _ in BLOCKS if s == "main"); nsub = len(BLOCKS) - nmain
FOOT = ["Lower is better for 'invented' and 'misquotes'; higher is better for 'cited a case that states the rule'. Misquote = the opinion does not contain the quoted words, or the case name is wrong.",
        "Sonnet 5 v7 rows via Claude Code; the v6-server Sonnet row via API (55 of 60 graded). Fable and Opus with tools via Claude Code with only the Syfert tools attached; their bare rows via API.",
        "GPT-6 and Gemini were not run with the tools. The few 'invented' cites in the Fable, Opus and GPT-6 rows are real cases cited at a wrong page or volume, not made-up cases.",
        "All rows re-graded with grader g10 (Sept 23): quote-matcher fixes, pin folding, twin cites, stricter name matching. 'Cited a case that states the rule' replaces the earlier 'found the right case'",
        "column: the earlier column credited only the one case each question was drawn from, which penalised citing the origin (e.g. Iqbal for Iqbal's own sentence); the new column credits any cited",
        "opinion that contains the proposition verbatim. Earlier-column values are in the repo report. MCP v7 rows: server upgraded 2026-09-23 (find_authority, verify_quote, cite_as).",
        "Five Gemma answers that were raw tool-call strings (a harness defect) were re-run (on the v7 server). Preliminary, Sept 23 2026. Grader hand-audited at ~90% precision.",
        "Harness, questions and raw results: github.com/Gwonk1/citebench  |  citebench by syfert.com (I run both the tool and the grader)."]
FOOT_H = 0.235 * len(FOOT) + 0.35   # 10.5 pt at linespacing 1.45 = 0.21 in per line, + bottom margin
H = 2.05 + 0.6 * nrows + 0.75 * nmain + 0.6 * nsub + 0.25 * len(BLOCKS) + 1.0 + FOOT_H
fig = plt.figure(figsize=(16, H), dpi=150, facecolor=SURF); ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off(); ax.set_xlim(0, 100); ax.set_ylim(0, 100)
fig.text(0.04, 1 - 0.35 / H, "Do AI models cite real law correctly?", fontsize=24, fontweight="bold", color=INK, va="top")
fig.text(0.04, 1 - 0.85 / H, "150 real legal propositions (Florida, federal, 10 other states). Every citation in every answer checked against 10.7M opinions.", fontsize=13, color=INK2, va="top")
HEAD = ["", "Questions", "Citations\nchecked", "Invented case\n(per 100 cites)", "Misquotes a real case\n(per 100 cites)", "Cited a case that\nstates the rule"]
cols = [4, 40, 51, 63, 78, 93]
U = 100 / H  # 1 inch in axis units
rh, gap = 0.6 * U, 0.25 * U
y = 100 - 1.6 * U
for i, h in enumerate(HEAD):
    ax.text(cols[i], y, h, ha="left" if i == 0 else "center", va="center", fontsize=13, color=INK2, fontweight="bold")
y -= rh * 0.75; ax.plot([3, 99], [y, y], color=INK, lw=1.2)
for header, style, rs in BLOCKS:
    y -= gap
    if style == "main":   # dark full-width band: block header, unlike any model row
        hh = 0.75 * U; y -= hh
        ax.add_patch(Rectangle((3, y), 96, hh * 0.86, color=HEADBG, lw=0, zorder=0))
        ax.text(cols[0], y + hh * 0.43, header, ha="left", va="center", fontsize=15.5, fontweight="bold", color="#ffffff", zorder=2)
    else:                 # sub-block: italic caption with a rule, no band
        hh = 0.6 * U; y -= hh
        ax.text(cols[0] + 1, y + hh * 0.45, header, ha="left", va="center", fontsize=13.5, style="italic", color=INK2, zorder=2)
        ax.plot([cols[0] + 1, 99], [y + hh * 0.05, y + hh * 0.05], color=LINE, lw=0.9)
    sub = style == "sub"
    for k, (name, lab, rid) in enumerate(rs):
        r = rows[rid]; y -= rh
        if k % 2 == 0: ax.add_patch(Rectangle((3, y), 96, rh, color=BAND, lw=0, zorder=0))
        t = ax.text(cols[0] + 1, y + rh * 0.5, name, ha="left", va="center", fontsize=15, fontweight="normal" if sub else "bold", color=INK2 if sub else INK, zorder=2)
        if lab:
            fig.canvas.draw(); bb = t.get_window_extent().transformed(ax.transData.inverted())
            ax.text(bb.x1 + 1.0, y + rh * 0.5, lab, ha="left", va="center", fontsize=12, color=INK2, zorder=2)
        vals = [(f"{r['n']}", None), (f"{r['cites']}", None), (f"{r['fab']:.1f}", tint("fab", r["fab"])), (f"{r['misgr']:.1f}", tint("mis", r["misgr"])), (f"{r['gold']:.0f}%", tint("gold", r["gold"]))]
        for i, (v, bg) in enumerate(vals, start=1):
            if bg: ax.add_patch(FancyBboxPatch((cols[i] - 5.2, y + rh * 0.12), 10.4, rh * 0.76, boxstyle="round,pad=0,rounding_size=0.6", color=bg, lw=0, zorder=1))
            ax.text(cols[i], y + rh * 0.5, v, ha="center", va="center", fontsize=15, color=INK, fontweight="bold" if bg else "normal", zorder=2)
        print(f"{header[:12]:12} | {name} {lab} | {rid} | {r['n']} | {r['cites']} | {r['fab']:.1f} | {r['misgr']:.1f} | {r['gold']:.1f}%")
    ax.plot([3, 99], [y, y], color=LINE, lw=0.6, zorder=1)
# legend for colours
ly = y - 0.45 * U
for i, (c, t) in enumerate(((GOOD, "good"), (WARN, "middling"), (BAD, "poor"))):
    ax.add_patch(FancyBboxPatch((4 + i * 11, ly - 0.15 * U), 2.2, 0.3 * U, boxstyle="round,pad=0,rounding_size=0.4", color=c, lw=0)); ax.text(7 + i * 11, ly, t, va="center", fontsize=12, color=INK2)
ax.text(4, ly - 0.45 * U, "\n".join(FOOT), fontsize=10.5, color=INK2, va="top", linespacing=1.45)
out = os.path.join(ROOT, "publish", "charts", "reddit_table.png"); fig.savefig(out, facecolor=SURF); print("wrote", out)
