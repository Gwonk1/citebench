#!/usr/bin/env python3
# usage: cd ~/projects/citebench && uv run --no-project --with matplotlib python publish/charts/make_reddit_table2.py   (headline table image, paired rows per model, colour-coded cells)
import os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def read_report(fname):
    """{(model, arm): row, run_id: row} from a report.py markdown table; columns found by header name."""
    out, idx = {}, None
    for l in open(os.path.join(ROOT, "results", fname)):
        if not l.startswith("| "): continue
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        if c[0] == "model" and "fabricated_rate" in c:
            idx = {k: i for i, k in enumerate(c)}; continue
        if idx is None or len(c) != len(idx) or ":" not in c[2]: continue
        p = lambda k: float(c[idx[k]].rstrip("%"))
        r = dict(n=int(c[idx["answered"]]), cites=int(c[idx["cites"]]), fab=p("fabricated_rate"), misgr=p("misgrounded_rate"), gold=p("gold_recall"))
        out.setdefault((c[0], c[1]), r); out[c[2]] = r
    return out
# Every row comes from the current results/report_150.md (grader g10); the last column is gold_equiv.
rows = read_report("report_150.md")
rows_g9 = rows

MODELS = [  # (display name, bare run_id, unused, MCP v7 run_id) -- order set by Graham 2026-09-23; v6-server tools rows dropped
    ("Claude Fable 5.1", "claude-fable-5-1:bare:v1", None, None),
    ("GPT-6 Astra", "gpt-6-astra:bare:v1", None, None),
    ("Gemini 3.1 Pro", "gemini-3.1-pro-or:bare:v1", None, None),
    ("Claude Opus 5.5", "claude-opus-5-5:bare:v1", None, "claude-opus-5-5-cc:mcp:v2"),
    ("Claude Sonnet 5", "claude-sonnet-5-cc:bare:v7", None, "claude-sonnet-5-cc:mcp:v7"),
    ("Gemma 4 26B, local", "local-gemma:bare:v1", None, "local-gemma:mcp:v3"),
]
SUBLABEL = {"Gemma 4 26B, local": "no web access"}
GOOD, WARN, BAD = "#d9f0d9", "#fdebc2", "#f6d0d0"
def tint(kind, v):
    if kind == "fab":  return GOOD if v < 1 else WARN if v < 5 else BAD
    if kind == "mis":  return GOOD if v < 5 else WARN if v < 15 else BAD
    return GOOD if v >= 85 else WARN if v >= 60 else BAD

SURF, INK, INK2, LINE, BAND = "#fcfcfb", "#0b0b0b", "#52514e", "#dddcd8", "#f3f2ef"
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
nrows = sum(sum(1 for k in ks if k) for _, *ks in MODELS)
H = 4.35 + 0.6 * nrows + 0.25 * len(MODELS)
fig = plt.figure(figsize=(16, H), dpi=150, facecolor=SURF); ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off(); ax.set_xlim(0, 100); ax.set_ylim(0, 100)
fig.text(0.04, 1 - 0.35 / H, "Syfert Case Hallucination Benchmark", fontsize=24, fontweight="bold", color=INK, va="top")
fig.text(0.04, 1 - 0.85 / H, "150 real legal propositions (Florida, federal, 10 other states). Every citation in every answer checked against 10.7M opinions.", fontsize=13, color=INK2, va="top")
HEAD = ["", "Questions", "Citations\nchecked", "Invented case\n(per 100 cites)", "Misquotes a real case\n(per 100 cites)", "Gold standard\ncase"]
cols = [4, 40, 51, 63, 78, 93]
rh, gap = 100 * 0.6 / H, 100 * 0.25 / H
y = 100 * (1 - 1.35 / H)
for i, h in enumerate(HEAD):
    ax.text(cols[i], y, h, ha="left" if i == 0 else "center", va="center", fontsize=13, color=INK2, fontweight="bold")
y -= rh * 0.75; ax.plot([3, 99], [y, y], color=INK, lw=1.2)
for name, bkey, tkey, vkey in MODELS:
    y -= gap
    n_lines = sum(1 for k in (bkey, tkey, vkey) if k)
    ax.add_patch(Rectangle((3, y - n_lines * rh), 96, n_lines * rh, color=BAND, lw=0, zorder=0))
    ax.text(cols[0] + 1, y - rh * 0.5, name, ha="left", va="center", fontsize=15, fontweight="bold", color=INK, zorder=2)
    if name in SUBLABEL and n_lines >= 2:  # second line under the model name
        ax.text(cols[0] + 1, y - rh * 0.98, SUBLABEL[name], ha="left", va="center", fontsize=12.5, style="italic", color=INK2, zorder=2)
    first = True
    for key, arm, sub in ((bkey, "bare", "on its own"), (vkey, "v7", "+ Syfert MCP v7")):
        if not key: continue
        y -= rh; r = rows[key]
        t = ax.text(cols[0] + 21, y + rh * 0.5, sub, ha="left", va="center", fontsize=13.5, color=INK2 if arm == "bare" else "#9a3a10", fontweight="normal" if arm == "bare" else "bold", zorder=2)
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
FOOT = ["Lower is better for 'invented' and 'misquotes'; higher is better for 'gold standard case'. Misquote = the opinion does not contain the quoted words, or the case name is wrong.", "'Gold standard case' = cited the case each question was drawn from (a real opinion courts cite for that proposition). Any other cited opinion that states the rule word for word is reported separately in the repo (gold_equiv).", "'+ Syfert MCP v7' rows via Claude Code (Opus, Sonnet) or local llama.cpp (Gemma) with only the Syfert tools attached; server upgraded 2026-09-23 (find_authority, verify_quote, cite_as).", "Bare rows via API except Sonnet (Claude Code). GPT-6, Gemini and Fable were not run with the v7 tools. The few 'invented' cites in the Fable, Opus and GPT-6 rows are real cases cited at a wrong page or volume.", 'All rows graded with grader g10 (Sept 23); every grader version is documented in the repo. Preliminary, Sept 23 2026. Grader hand-audited at ~90% precision.', 'Harness, questions and raw results: github.com/Gwonk1/citebench  |  citebench by syfert.com (I run both the tool and the grader).']
fig.text(0.04, 0.25 / H, "\n".join(FOOT), fontsize=10.5, color=INK2, va="bottom")
out = os.path.join(ROOT, "publish", "charts", "reddit_table.png"); fig.savefig(out, facecolor=SURF); print("wrote", out)
