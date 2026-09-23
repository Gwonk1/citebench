#!/usr/bin/env python3
# usage: uv run --no-project --with matplotlib python publish/charts/make_charts.py [--report results/report_150.md] [--db results/results.db] [--out publish/charts]
"""Render the four citebench publication charts (SVG + 2x PNG, light + _dark) from report_150.md.

Headline rates come from the report's markdown table (so a regrade + `report.py --max-qid q0150
--out results/report_150.md` re-renders them). The one split the report does not print -- name
mismatches vs absent quotes -- is read READ-ONLY from results.db on the same qid slice, and cross-
checked against the report's misgrounded_rate. The Fable reporter-pagination figure (chart 4) uses
the hand-audited numbers from docs/METHODOLOGY.md section 4 (constants below).
"""
import argparse
import math
import os
import re
import sqlite3
import sys

import logging
import matplotlib
matplotlib.use("Agg")
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import PathPatch, Polygon
from matplotlib.path import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATE = "Sept 22 2026"
SOURCE = "citebench / syfert.com"
EXCLUDE = {("gemini-3.8-flash-or", "mcp")}  # 37 of 40 answers errored; n=3 is not a result

# docs/METHODOLOGY.md section 4: hand audit of Fable 5.1's 755 bare citations
FABLE_AUDIT = {"cites": 755, "resolved": 735, "unindexed": 18, "wrong_page": 2}
PAGINATION_NOTE = "So. 3d pagination absent from free sources after vol. ~277 (2019)"

NAMES = {
    "claude-fable-5-1": "Claude Fable 5.1", "claude-opus-5-5": "Claude Opus 5.5",
    "claude-sonnet-5-or": "Sonnet 5", "deepseek-v4-pro": "DeepSeek 4 Pro",
    "deepseek-v4.1-flash-or": "DeepSeek 4.1 Flash", "gemini-3.1-pro-or": "Gemini 3.1 Pro",
    "gemini-3.8-flash-or": "Gemini 3.8 Flash", "gpt-6-astra": "GPT-6 Astra",
    "local-gemma": "Gemma 4 26B local", "qwen3.8-flash-or": "Qwen 3.8 Flash",
    "qwen3.8-max": "Qwen 3.8 Max",
    "claude-fable-5-1-cc": "Claude Fable 5.1 (Claude Code)", "claude-opus-5-5-cc": "Claude Opus 5.5 (Claude Code)",
}
FRONTIER = {"claude-fable-5-1", "claude-opus-5-5", "gpt-6-astra", "gemini-3.1-pro-or",
            "deepseek-v4-pro", "qwen3.8-max"}

# dataviz reference palette (validated: scripts/validate_palette.js, light + dark)
THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
                  grid="#e1e0d9", axis="#c3c2b7", neutral="#c3c2b7", bare="#898781",
                  syfert="#2a78d6", red="#e34948", violet="#4a3aa7", orange="#eb6834",
                  aqua="#1baf7a", yellow="#eda100"),
    "dark": dict(surface="#1a1a19", ink="#ffffff", ink2="#c3c2b7", muted="#898781",
                 grid="#2c2c2a", axis="#383835", neutral="#52514e", bare="#898781",
                 syfert="#3987e5", red="#e66767", violet="#9085e9", orange="#d95926",
                 aqua="#199e70", yellow="#c98500"),
}

W_IN, DPI = 10.0, 120          # 1200 px at 1x; PNG written at 2x (240 dpi)


# ---------------------------------------------------------------- data
def pct(s):
    s = s.strip()
    return None if s in ("n/a", "") else float(s.rstrip("%")) / 100


def parse_report(path):
    txt = open(path, encoding="utf-8").read()
    m = re.search(r"questions <= (q\d+)", txt)
    max_qid = m.group(1) if m else None
    rows, deltas = {}, {}
    sec = None
    for line in txt.splitlines():
        if line.startswith("## Metrics"):
            sec = "m"; hdr = None; continue
        if line.startswith("## bare -> mcp"):
            sec = "d"; hdr = None; continue
        if not line.startswith("|") or sec is None:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0] == "model":
            hdr = cells; continue
        if set(cells[0]) <= {"-"}:
            continue
        r = dict(zip(hdr, cells))
        if sec == "m":
            rows[(r["model"], r["arm"])] = {
                "run": r["run"], "graded": int(r["graded"]), "cites": int(r["cites"]),
                "fab": pct(r["fabricated_rate"]), "fab_strict": pct(r["fabricated_strict_rate"]),
                "mis": pct(r["misgrounded_rate"]), "para": pct(r["paraphrase_share"]),
                "recall": pct(r["gold_recall"]),
            }
        else:
            deltas[r["model"]] = {k: v for k, v in r.items()}
    return max_qid, rows, deltas


def db_splits(db, rows, max_qid):
    """name-mismatch / quote-absent / fabricated / unindexed counts per run (read-only)."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    out = {}
    for key, r in rows.items():
        q = ("SELECT count(*), sum(n_cites), sum(n_fabricated), sum(n_unindexed), "
             "sum(n_name_mismatch), sum(n_quote_absent) FROM grades WHERE run_id=?")
        args = [r["run"]]
        if max_qid:
            q += " AND qid <= ?"; args.append(max_qid)
        n, c, fab, unidx, nm, qa = [x or 0 for x in con.execute(q, args).fetchone()]
        out[key] = dict(n=n, cites=c, fab=fab, unidx=unidx, nm=nm, qa=qa)
        # the report is the source of truth; refuse to plot a DB that disagrees with it
        if c != r["cites"] or n != r["graded"] or (r["mis"] is not None and c and
                                                    abs((nm + qa) / c - r["mis"]) > 0.0006):
            sys.exit(f"results.db disagrees with report for {r['run']}: regenerate report_150.md first")
    return out


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def wil_rate(rate, n):
    return wilson(round(rate * n), n)


# ---------------------------------------------------------------- drawing helpers
def setup_fonts():
    for fam in ("Inter", "DejaVu Sans"):
        try:
            font_manager.findfont(fam, fallback_to_default=False)
            break
        except Exception:
            continue
    plt.rcParams.update({
        "font.family": [fam, "DejaVu Sans"], "font.size": 12, "svg.fonttype": "none",
        "axes.linewidth": 1, "xtick.major.size": 0, "ytick.major.size": 0,
        "xtick.major.pad": 6, "ytick.major.pad": 8,
    })


def new_fig(t, h_in, left=0.25, right=0.95, top=None, bottom=None):
    fig = plt.figure(figsize=(W_IN, h_in), dpi=DPI, facecolor=t["surface"])
    top = top if top is not None else 1 - 1.15 / h_in
    bottom = bottom if bottom is not None else 0.85 / h_in
    return fig, dict(left=left, right=right, top=top, bottom=bottom)


def style_ax(ax, t, xgrid=True):
    ax.set_facecolor(t["surface"])
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(t["axis"])
    ax.tick_params(colors=t["muted"], labelsize=11)
    if xgrid:
        ax.grid(axis="x", color=t["grid"], linewidth=1, linestyle="-")
        ax.set_axisbelow(True)


def header(fig, t, title, subtitle):
    fig.text(0.025, 1 - 0.28 / fig.get_figheight(), title, fontsize=17, fontweight="semibold",
             color=t["ink"], va="top", ha="left")
    fig.text(0.025, 1 - 0.68 / fig.get_figheight(), subtitle, fontsize=11.5, color=t["ink2"],
             va="top", ha="left", linespacing=1.35)
    fig.text(0.025, 0.22 / fig.get_figheight(), SOURCE, fontsize=10, color=t["muted"],
             va="bottom", ha="left")


def px(ax):
    """data units per pixel in x and y (valid once limits + subplot position are fixed)."""
    tr = ax.transData.inverted()
    (x0, y0), (x1, y1) = tr.transform([(0, 0), (1, 1)])
    return abs(x1 - x0), abs(y1 - y0)


def hbar(ax, y, x0, x1, h, color, round_end=True, gap_l=0, gap_r=0):
    """horizontal bar, 4px rounded data-end, square at the baseline; gaps in px (surface gap)."""
    dx, dy = px(ax)
    x0 += gap_l * dx; x1 -= gap_r * dx
    if x1 <= x0:
        return
    rx = min(4 * dx, (x1 - x0) / 2) if round_end else 0
    ry = min(4 * dy, h / 2) if round_end else 0
    k = 0.5523
    yb, yt = y - h / 2, y + h / 2
    v = [(x0, yb), (x1 - rx, yb)]
    c = [Path.MOVETO, Path.LINETO]
    if rx:
        v += [(x1 - rx + k * rx, yb), (x1, yb + ry - k * ry), (x1, yb + ry), (x1, yt - ry),
              (x1, yt - ry + k * ry), (x1 - rx + k * rx, yt), (x1 - rx, yt)]
        c += [Path.CURVE4] * 3 + [Path.LINETO] + [Path.CURVE4] * 3
    else:
        v += [(x1, yt)]; c += [Path.LINETO]
        v[1] = (x1, yb)
    v += [(x0, yt), (x0, yb)]
    c += [Path.LINETO, Path.CLOSEPOLY]
    ax.add_patch(PathPatch(Path(v, c), facecolor=color, edgecolor="none", zorder=3))


def whisker(ax, y, lo, hi, color, cap=0.09, lw=1.3, z=5):
    ax.plot([lo, hi], [y, y], color=color, lw=lw, solid_capstyle="butt", zorder=z)
    ax.plot([lo, lo], [y - cap, y + cap], color=color, lw=lw, zorder=z)
    ax.plot([hi, hi], [y - cap, y + cap], color=color, lw=lw, zorder=z)


def dot(ax, x, y, color, t, s=90, marker="o", z=6):
    ax.scatter([x], [y], s=s, color=color, marker=marker, zorder=z,
               edgecolors=t["surface"], linewidths=2)


def legend(fig, t, items, x0, y0, xmax=0.975, row_h_in=0.30):
    """items: (kind, color, label), kind in bar|D|o|wh. Widths measured, wraps at xmax."""
    r = fig.canvas.get_renderer()
    fw = fig.get_figwidth() * fig.dpi
    x, y = x0, y0
    for kind, c, lab in items:
        txt = fig.text(0, 0, lab, fontsize=10.5, color=t["ink2"], va="center")
        w = txt.get_window_extent(renderer=r).width / fw
        if x > x0 and x + 0.03 + w > xmax:
            x, y = x0, y - row_h_in / fig.get_figheight()
        txt.set_position((x + 0.03, y))
        if kind == "bar":
            fig.patches.append(matplotlib.patches.FancyBboxPatch((x, y - 0.006), 0.022, 0.012,
                               boxstyle="round,pad=0,rounding_size=0.003", transform=fig.transFigure,
                               facecolor=c, edgecolor="none"))
        elif kind in ("D", "o"):
            fig.add_artist(matplotlib.lines.Line2D([x + 0.011], [y], marker=kind,
                           markersize=7 if kind == "D" else 9, color=c,
                           markeredgecolor=t["surface"], transform=fig.transFigure))
        else:
            fig.add_artist(matplotlib.lines.Line2D([x, x + 0.022], [y, y], color=c, lw=1.2,
                                                   transform=fig.transFigure))
        x += 0.03 + w + 0.03


def pfmt(x):
    return f"{100 * x:.1f}%"


def save(fig, outdir, name, mode, title, desc):
    base = os.path.join(outdir, name + ("_dark" if mode == "dark" else ""))
    fig.savefig(base + ".svg", facecolor=fig.get_facecolor(),
                metadata={"Title": title, "Description": desc, "Date": None})
    fig.savefig(base + ".png", dpi=DPI * 2, facecolor=fig.get_facecolor())
    plt.close(fig)
    return [base + ".svg", base + ".png"]


# ---------------------------------------------------------------- chart 1
def chart_headline(rows, t, mode, outdir):
    mcp = sorted([k for k in rows if k[1] == "mcp"], key=lambda k: rows[k]["mis"])
    bare = sorted([k for k in rows if k[1] == "bare"], key=lambda k: rows[k]["mis"])
    order = [("hdr", "With Syfert's MCP tools")] + [("row", k) for k in mcp] + \
            [("hdr", "Bare model, no tools")] + [("row", k) for k in bare]
    h = 1.9 + 0.46 * len(order)
    fig, box = new_fig(t, h, left=0.30, right=0.93, bottom=1.25 / h, top=1 - 1.35 / h)
    ax = fig.add_axes([box["left"], box["bottom"], box["right"] - box["left"], box["top"] - box["bottom"]])
    style_ax(ax, t)
    n = len(order)
    ax.set_ylim(n - 0.4, -0.6)
    ax.set_xlim(0, 0.80)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
    ax.set_yticks([])
    best_bare = min(rows[k]["mis"] for k in bare if k[0] in FRONTIER)
    for i, (kind, k) in enumerate(order):
        if kind == "hdr":
            ax.text(-0.005, i + 0.1, k, transform=ax.get_yaxis_transform(), ha="right", va="center",
                    fontsize=11.5, fontweight="semibold", color=t["ink2"])
            continue
        r = rows[k]
        col = t["syfert"] if k[1] == "mcp" else t["bare"]
        name = NAMES.get(k[0], k[0]) + (" + Syfert" if k[1] == "mcp" else "")
        ax.text(-0.012, i - 0.02, name, transform=ax.get_yaxis_transform(), ha="right", va="center",
                fontsize=12, color=t["ink"], fontweight="semibold" if k[1] == "mcp" else "normal")
        ax.text(-0.012, i + 0.3, f"{r['cites']} cites · {r['graded']} q", transform=ax.get_yaxis_transform(),
                ha="right", va="center", fontsize=9.5, color=t["muted"])
        yb = i - 0.1
        hbar(ax, yb, 0, r["mis"], 0.36, col)
        lo, hi = wil_rate(r["mis"], r["cites"])
        whisker(ax, yb, lo, hi, t["ink2"], cap=0.08)
        ax.text(hi + 0.008, yb, pfmt(r["mis"]), va="center", ha="left", fontsize=11, color=t["ink"])
        yf = i + 0.25
        flo, fhi = wil_rate(r["fab"], r["cites"])
        ax.plot([flo, fhi], [yf, yf], color=t["red"], lw=1.2, zorder=4, solid_capstyle="butt")
        dot(ax, r["fab"], yf, t["red"], t, s=48, marker="D")
    ax.axvline(best_bare, color=t["muted"], lw=1, zorder=2)
    ax.text(best_bare + 0.004, -0.55, f"best bare model {pfmt(best_bare)}", fontsize=9.5,
            color=t["muted"], va="top", ha="left")
    legend(fig, t, [("bar", t["syfert"], "misgrounded, + Syfert"), ("bar", t["bare"], "misgrounded, bare"),
                    ("D", t["red"], "fabricated"), ("wh", t["ink2"], "95% Wilson interval")],
           box["left"], 0.62 / h)
    title = "With Syfert's tools, misgrounded citations fall to 2–6% for every model tested"
    sub = (f"Misgrounded = wrong case name or a quote not in the opinion, share of all citations; "
           f"fabricated = citation resolves to no case.\nBare: 150 questions (Flash models 60 or 40); "
           f"+ Syfert: 55–150 graded answers. Preliminary, {DATE}.")
    header(fig, t, title, sub)
    desc = "; ".join(f"{NAMES.get(k[0], k[0])}{' + Syfert' if k[1] == 'mcp' else ''}: misgrounded "
                     f"{pfmt(rows[k]['mis'])}, fabricated {pfmt(rows[k]['fab'])} of {rows[k]['cites']} cites"
                     for _, k in order if _ == "row")
    return save(fig, outdir, "headline_bars", mode, title, desc)


# ---------------------------------------------------------------- chart 2
def chart_failure_mix(rows, splits, t, mode, outdir):
    """two bars per bare model: unresolved cites (fabricated + real-but-unindexed) vs misgrounded
    (name mismatch + absent quotes, split paraphrase / wrong wording). Not stacked into one bar:
    misgrounded counts quotes, so a fabricated cite can also carry absent quotes."""
    bare = [k for k in rows if k[1] == "bare"]
    data = []
    for k in bare:
        s, r = splits[k], rows[k]
        para = round((r["para"] or 0) * s["qa"])
        data.append(dict(k=k, c=s["cites"], q=r["graded"], fab=s["fab"], nm=s["nm"],
                         wrong=s["qa"] - para, para=para, unidx=s["unidx"]))
    data.sort(key=lambda d: (d["fab"] / d["c"], (d["nm"] + d["wrong"] + d["para"]) / d["c"]))
    segA = [("fab", "red", "fabricated: no such case"), ("unidx", "yellow", "real, not in free index")]
    segB = [("nm", "violet", "wrong case name"), ("wrong", "orange", "quote: wording not in opinion"),
            ("para", "aqua", "quote: paraphrase in quote marks")]
    h = 2.5 + 0.68 * len(data)
    fig, box = new_fig(t, h, left=0.25, right=0.86, bottom=1.5 / h, top=1 - 1.35 / h)
    ax = fig.add_axes([box["left"], box["bottom"], box["right"] - box["left"], box["top"] - box["bottom"]])
    style_ax(ax, t)
    ax.set_ylim(len(data) - 0.45, -0.55)
    ax.set_xlim(0, 0.8)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
    ax.set_yticks([])
    bh = 0.27
    for i, d in enumerate(data):
        ax.text(-0.012, i - 0.07, NAMES.get(d["k"][0], d["k"][0]), transform=ax.get_yaxis_transform(),
                ha="right", va="center", fontsize=12, color=t["ink"],
                fontweight="semibold" if d["k"][0] in FRONTIER else "normal")
        ax.text(-0.012, i + 0.25, f"{d['c']} cites · {d['q']} q", transform=ax.get_yaxis_transform(),
                ha="right", va="center", fontsize=9.5, color=t["muted"])
        for y, segs, kk, lab in ((i - 0.16, segA, ["fab"], "invented"),
                                 (i + 0.16, segB, ["nm", "wrong", "para"], "misgrounded")):
            present = [sg for sg in segs if d[sg[0]]]
            x = 0.0
            for j, (key, cname, _) in enumerate(present):
                w = d[key] / d["c"]
                last = j == len(present) - 1
                hbar(ax, y, x, x + w, bh, t[cname], round_end=last, gap_l=1 if j else 0,
                     gap_r=0 if last else 1)
                x += w
            k = sum(d[z] for z in kk)
            lo, hi = wilson(k, d["c"])
            whisker(ax, y, lo, hi, t["ink2"], cap=0.07, lw=1.1)
            ax.text(max(x, hi) + 0.008, y, f"{pfmt(k / d['c'])} {lab}", va="center", ha="left",
                    fontsize=10.5, color=t["ink"] if lab == "misgrounded" else t["ink2"])
    legend(fig, t, [("bar", t[c], lab) for _, c, lab in segA + segB] +
           [("wh", t["ink2"], "95% Wilson interval")], box["left"], 0.85 / h)
    title = "Frontier models rarely invent cases. They misquote real ones."
    sub = (f"Bare models, no tools. Top bar: citations that resolve to no case. Bottom bar: wrong names "
           f"and quotes not in the opinion,\nper citation. 150 questions each (Flash models 60 or 40). "
           f"Preliminary, {DATE}.")
    header(fig, t, title, sub)
    desc = "; ".join(f"{NAMES.get(d['k'][0])}: of {d['c']} cites, {d['fab']} fabricated, {d['unidx']} unindexed, "
                     f"{d['nm']} wrong name, {d['wrong']} wrong quote wording, {d['para']} paraphrase in quotes"
                     for d in data)
    return save(fig, outdir, "fab_vs_misgrounded", mode, title, desc), data


# ---------------------------------------------------------------- chart 3
def chart_bare_vs_mcp(rows, t, mode, outdir):
    models = ["local-gemma", "qwen3.8-flash-or", "deepseek-v4.1-flash-or", "claude-sonnet-5-or"]
    ref = rows[("claude-fable-5-1", "bare")]
    metrics = [("fab", "Fabricated", "lower is better", "cites"),
               ("mis", "Misgrounded", "lower is better", "cites"),
               ("recall", "Gold-case recall", "higher is better", "graded")]
    h = 7.3
    fig = plt.figure(figsize=(W_IN, h), dpi=DPI, facecolor=t["surface"])
    left, right, top, bottom = 0.215, 0.975, 1 - 2.35 / h, 1.25 / h
    gap = 0.035
    pw = (right - left - 2 * gap) / 3
    for p, (key, label, better, nkey) in enumerate(metrics):
        ax = fig.add_axes([left + p * (pw + gap), bottom, pw, top - bottom])
        style_ax(ax, t)
        ax.set_xlim(0, 1)
        ax.set_ylim(len(models) - 0.4, -0.75)
        ax.set_xticks([0, 0.5, 1])
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
        ax.set_yticks([])
        ax.set_title(label, loc="left", fontsize=13, fontweight="semibold", color=t["ink"], pad=18)
        ax.text(0, 1.015, better, transform=ax.transAxes, fontsize=9.5, color=t["muted"], va="bottom")
        ax.axvline(ref[key], color=t["muted"], lw=1, zorder=2)
        ax.text(ref[key] + (0.02 if ref[key] < 0.6 else -0.02), -0.62,
                f"Fable 5.1 bare {pfmt(ref[key])}", fontsize=9, color=t["muted"], va="center",
                ha="left" if ref[key] < 0.6 else "right")
        for i, m in enumerate(models):
            if p == 0:
                ax.text(-0.06, i, NAMES[m], transform=ax.get_yaxis_transform(), ha="right",
                        va="center", fontsize=12, color=t["ink"])
                if ("claude-sonnet-5-or", "bare") not in rows and m == "claude-sonnet-5-or":
                    ax.text(-0.06, i + 0.3, "not run bare", transform=ax.get_yaxis_transform(),
                            ha="right", va="center", fontsize=9.5, color=t["muted"])
            b, s = rows.get((m, "bare")), rows.get((m, "mcp"))
            if b and s:
                ax.plot([b[key], s[key]], [i, i], color=t["axis"], lw=2, zorder=3,
                        solid_capstyle="round")
            for arm, r, col, dy, va in (("bare", b, t["bare"], -0.2, "bottom"),
                                        ("mcp", s, t["syfert"], 0.2, "top")):
                if not r:
                    continue
                lo, hi = wil_rate(r[key], r[nkey])
                whisker(ax, i, lo, hi, col, cap=0.1, lw=1.2, z=4)
                dot(ax, r[key], i, col, t, s=80)
                ax.text(min(max(r[key], 0.05), 0.95), i + dy, pfmt(r[key]), fontsize=9.5,
                        color=t["ink2"], ha="center", va=va)
    legend(fig, t, [("o", t["bare"], "bare, no tools"), ("o", t["syfert"], "+ Syfert MCP tools"),
                    ("wh", t["ink2"], "95% Wilson interval")], left, 0.62 / h)
    ns = ", ".join(f"{NAMES[m].split()[0]} {rows[(m, 'mcp')]['graded']}" for m in models if (m, "mcp") in rows)
    title = "Same model, with and without Syfert's tools"
    sub = (f"Rates over all citations; recall = share of questions citing the gold case. "
           f"\nGraded answers with tools: {ns}; bare: Gemma 150, Qwen / DeepSeek 60.\n"
           f"Sonnet 5 was run with tools only. Preliminary, {DATE}.")
    header(fig, t, title, sub)
    desc = "; ".join(f"{NAMES[m]} {arm}: fabricated {pfmt(r['fab'])}, misgrounded {pfmt(r['mis'])}, "
                     f"gold recall {pfmt(r['recall'])}" for m in models for arm in ("bare", "mcp")
                     for r in [rows.get((m, arm))] if r)
    return save(fig, outdir, "bare_vs_mcp", mode, title, desc)


# ---------------------------------------------------------------- chart 4
def chart_index_gap(t, mode, outdir):
    a = FABLE_AUDIT
    unres = a["unindexed"] + a["wrong_page"]
    h = 4.6
    fig = plt.figure(figsize=(W_IN, h), dpi=DPI, facecolor=t["surface"])
    ax = fig.add_axes([0.05, 1.05 / h, 0.90, 1 - 2.45 / h])
    ax.set_facecolor(t["surface"])
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(2.5, -0.55)
    C = a["cites"]
    # row 0: all citations
    x_res = a["resolved"] / C
    hbar(ax, 0, 0, x_res, 0.5, t["neutral"], round_end=False, gap_r=1)
    hbar(ax, 0, x_res, x_res + a["unindexed"] / C, 0.5, t["yellow"], round_end=False, gap_l=1, gap_r=1)
    hbar(ax, 0, x_res + a["unindexed"] / C, 1, 0.5, t["red"], gap_l=1)
    ax.text(0.012, 0, f"{a['resolved']} resolved by volume and page", va="center", ha="left",
            fontsize=12, color=t["ink"])
    ax.text(0, -0.42, f"All {C} citations Claude Fable 5.1 gave (bare, 150 questions)", fontsize=11,
            color=t["ink2"], va="bottom")
    # zoom connector
    ax.add_patch(Polygon([(x_res, 0.27), (1, 0.27), (1, 1.15), (0, 1.15)], closed=True,
                         facecolor=t["grid"], edgecolor="none", alpha=0.55, zorder=1))
    # row 1: the unresolved 20, zoomed
    lo, hi = wilson(a["unindexed"], C)
    xu = a["unindexed"] / unres
    hbar(ax, 1.4, 0, xu, 0.5, t["yellow"], round_end=False, gap_r=1)
    hbar(ax, 1.4, xu, 1, 0.5, t["red"], gap_l=1)
    ax.text(0, 1.1, f"The {unres} the reporter index could not resolve", fontsize=11, color=t["ink2"],
            va="bottom")
    ax.text(0.012, 1.4, f"{a['unindexed']} real cases, not in the free index "
            f"({pfmt(a['unindexed'] / C)} of all cites, 95% CI {pfmt(lo)}–{pfmt(hi)})",
            va="center", ha="left", fontsize=12, color="#0b0b0b")
    ax.text(xu + (1 - xu) / 2, 1.4, f"{a['wrong_page']}", va="center", ha="center", fontsize=12,
            color="#ffffff" if mode == "light" else "#0b0b0b", fontweight="semibold")
    ax.text(1, 1.72, f"{a['wrong_page']} real cases cited at the wrong page", fontsize=10.5,
            color=t["ink2"], ha="right", va="top")
    ax.text(0, 2.05, PAGINATION_NOTE + ". 17 of the 18 were decided 2018–2022.", fontsize=11.5,
            color=t["ink"], va="top", fontweight="semibold")
    ax.text(0, 2.32, "A free citation lookup answers these 18 real cases exactly as it answers "
            "an invented one: \"not found\".", fontsize=10.5, color=t["ink2"], va="top")
    title = "The free index lags the reporters: 2.4% of real citations can't be looked up"
    sub = (f"Claude Fable 5.1, bare, n = {C} citations in 150 answers. Unresolved cites matched by "
           f"case name and year\n(METHODOLOGY §4). Preliminary, {DATE}.")
    header(fig, t, title, sub)
    desc = (f"Of {C} citations, {a['resolved']} resolved, {a['unindexed']} real but unindexed, "
            f"{a['wrong_page']} wrong page. {PAGINATION_NOTE}.")
    return save(fig, outdir, "index_gap", mode, title, desc)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", default=os.path.join(ROOT, "results", "report_150.md"))
    ap.add_argument("--db", default=os.path.join(ROOT, "results", "results.db"))
    ap.add_argument("--out", default=HERE)
    a = ap.parse_args()
    setup_fonts()
    max_qid, rows, deltas = parse_report(a.report)
    for k in EXCLUDE:
        rows.pop(k, None)
    splits = db_splits(a.db, rows, max_qid)
    os.makedirs(a.out, exist_ok=True)
    files = []
    for mode, t in THEMES.items():
        files += chart_headline(rows, t, mode, a.out)
        f, mix = chart_failure_mix(rows, splits, t, mode, a.out)
        files += f
        files += chart_bare_vs_mcp(rows, t, mode, a.out)
        files += chart_index_gap(t, mode, a.out)
    print("\n".join(files))
    print("\n# chart 2 counts (bare): model cites fab name wrong_wording paraphrase unindexed")
    for d in mix:
        print(d["k"][0], d["c"], d["fab"], d["nm"], d["wrong"], d["para"], d["unidx"])


if __name__ == "__main__":
    main()
