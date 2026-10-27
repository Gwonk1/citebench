#!/usr/bin/env python3
# usage: python3 make_report.py   (after score.py; writes results/results_table.md, results/index.html, refreshes README.md between markers)
"""Render the LePhantomCite results: a markdown table block (spliced into README.md between <!-- RESULTS --> markers)
and the static isyfert.com page (light + dark via :root[data-theme="dark"] and prefers-color-scheme, phone friendly)."""
import json, os, html, datetime as dt
import lp_common as L

ARMS = [  # (run_id, label, notes)
    ("syfert:strict:test:v1", "Syfert check_brief alone, strict mapping", "no LLM; fabricated / name mismatch / absent quote"),
    ("syfert:broad:test:v1", "Syfert check_brief alone, broad mapping", "strict + unresolved, near quotes, pin failures, proposition mismatch"),
    ("claudecode-opus:bare:test:v1", "Claude Code harness (subscription) Opus 5.5, non-agentic", "claude -p, no tools; paper prompt"),
    ("claudecode-opus:mcp:test:v1", "Claude Code harness (subscription) Opus 5.5, agentic + Syfert MCP (8 tools, 30 turns)", "claude -p --strict-mcp-config; Claude Code's own system prompt/harness, not a raw API loop"),
    ("claudecode-opus48:bare:test:pre-mcp80", "Claude Code harness (subscription) Opus 4.8 (the paper's model), non-agentic", "claude -p, no tools; tools as of mcp79 ff954bdd"),
    ("claudecode-opus48:mcp:test:pre-mcp80", "Claude Code harness (subscription) Opus 4.8, agentic + Syfert MCP (8 tools, 30 turns)", "same harness as the Opus 5.5 row; ran 21:40–~01:10 UTC 10-16/17 with tools as of mcp80 (driver 2c1084bb, lib 7f8a8c36) — NOT mcp79 despite the tag; mcp81 (quotes/pincites) was live 23:51–00:19 UTC (~examples 180–250) before its kill file restored mcp80 behaviour"),
    ("claudecode-opus:mcp:test:post-mcp84", "Claude Code harness (subscription) Opus 5.5, agentic + Syfert MCP — tools as of mcp84 (10-17)", "same harness and prompt as the 10-16 row; only the Syfert tools changed (mcp80–84)"),
    ("syfert:strict:test:post-mcp82", "Syfert check_brief alone, strict — tools as of mcp82 (10-17)", "no LLM"),
    ("syfert:strict:test:post-mcp84b", "Syfert check_brief alone, strict — tools as of mcp84b (10-17)", "no LLM"),
    ("syfert:strict:test:post-mcp84b-v2", "Syfert check_brief alone, strict + near quotes / pin mismatches — tools as of mcp84b (10-17)", "no LLM; mapping v2"),
    ("claudecode-opus:mcp:subset130:v1", "Claude Code harness (subscription) Opus 5.5, agentic + Syfert MCP (130-example subset)", "stratified third, seed 20261016"),
    ("local-gemma:bare:test:nothink", "Gemma 4 E4B (Q4_0, local), non-agentic", "thinking off, max_tokens 1500"),
    ("local-gemma:mcp:test:nothink2", "Gemma 4 E4B (Q4_0, local), agentic + Syfert MCP (4 tools, 15 turns)", "thinking off; 8k context"),
]
PILOTS = [("claude-opus-5-5:bare:pilot20:v1", "Opus 5.5 non-agentic (raw API; key ran out of credit)"), ("claude-opus-5-5:mcp:pilot20:v1", "Opus 5.5 agentic (raw API; 17/20, credit ran out)"),
          ("claudecode-opus:bare:pilot20:v1", "Claude Code (subscription) Opus 5.5 non-agentic"), ("claudecode-opus:mcp:pilot20:v1", "Claude Code (subscription) Opus 5.5 agentic"),
          ("local-gemma:bare:pilot20:nothink", "Gemma E4B non-agentic"), ("local-gemma:mcp:pilot20:nothink3", "Gemma E4B agentic"),
          ("syfert:strict:pilot20:v1", "Syfert strict"), ("syfert:broad:pilot20:v1", "Syfert broad")]
PAPER = [  # Table 2 (test, n=390): label, P, R, F1 with +- half-widths
    ("GPT-5 agentic (BOED, 30 steps)", (40.8, 4.3), (84.4, 4.2), (55.0, 4.2)),
    ("GPT-5 non-agentic", (36.9, 4.5), (58.2, 5.2), (45.2, 4.2)),
    ("Claude Code / Opus 4.8 agentic (WebSearch + CourtListener MCP)", (76.1, 5.6), (62.8, 5.6), (68.8, 4.6)),
    ("Qwen3.6-27B agentic", (28.9, 4.1), (65.0, 5.1), (40.0, 4.4)),
    ("Qwen3.6-27B non-agentic", (45.9, 7.8), (31.5, 5.4), (37.4, 5.7)),
    ("Gemini 2.5 Flash agentic", (16.9, 2.4), (66.9, 5.1), (27.0, 3.3)),
    ("GPT-OSS 120B agentic", (21.1, 3.2), (55.1, 5.8), (30.5, 4.0)),
    ("Qwen3-8B agentic", (12.0, 2.2), (41.1, 6.0), (18.6, 3.1)),
]
PAPER_TYPES = {  # Table 8 recall by type (agentic)
    "GPT-5 agentic": {"non_existent_citation": 100.0, "case_name_mismatch": 100.0, "wrong_pincite": 52.8, "misquote": 95.2, "content_misrepresentation": 83.2},
    "Claude Code / Opus 4.8": {"non_existent_citation": 93.5, "case_name_mismatch": 83.8, "wrong_pincite": 3.6, "misquote": 71.7, "content_misrepresentation": 66.4},
    "Qwen3.6-27B agentic": {"non_existent_citation": 100.0, "case_name_mismatch": 96.5, "wrong_pincite": 50.9, "misquote": 64.3, "content_misrepresentation": 48.9},
}
TYPE_LABEL = {"non_existent_citation": "Non-existent", "case_name_mismatch": "Name mismatch", "wrong_pincite": "Pincite",
              "misquote": "Misquote", "content_misrepresentation": "Content"}


def pct(x):
    return f"{100 * x:.1f}"


def ci(d, k):
    lo, hi = d["ci95"][k]
    return f"{pct(lo)}–{pct(hi)}"


def main():
    scores = {s["run_id"]: s for s in json.load(open(os.path.join(L.RESULTS, "scores.json")))}
    con = L.open_db()
    cfg = {r: json.loads(c) for r, c in con.execute("SELECT run_id, config_json FROM runs")}
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    # ---------------- markdown
    md = [f"_Generated {now} by make_report.py from results/scores.json (paper matching rule; 95% bootstrap CIs over examples, 2000 resamples)._\n",
          "| Arm | n | P % | R % | F1 % | P CI | R CI | F1 CI | repo-rule F1 | errors | cost $ (Claude Code: nominal, subscription) |", "|---|---:|---:|---:|---:|---|---|---|---:|---:|---:|"]
    rows_html = []
    for run_id, label, note in ARMS:
        s = scores.get(run_id)
        if not s:
            md.append(f"| {label} | – | not run | | | | | | | | |")
            rows_html.append(f"<tr><td>{html.escape(label)}<div class=note>{html.escape(note)}</div></td><td colspan=9 class=mut>not run</td></tr>")
            continue
        d = s["paper"]
        md.append(f"| {label}{' — ' + note if note else ''} | {s['n']} | {pct(d['precision'])} | {pct(d['recall'])} | **{pct(d['f1'])}** | "
                  f"{ci(d, 'p')} | {ci(d, 'r')} | {ci(d, 'f1')} | {pct(s['repo']['f1'])} | {s['n_error']} | {s['cost_usd']:.2f} |")
        rows_html.append(f"<tr><td>{html.escape(label)}<div class=note>{html.escape(note)}</div></td><td class=num>{s['n']}</td>"
                         f"<td class=num>{pct(d['precision'])}</td><td class=num>{pct(d['recall'])}</td><td class='num b'>{pct(d['f1'])}</td>"
                         f"<td class=ci>{ci(d, 'p')}</td><td class=ci>{ci(d, 'r')}</td><td class=ci>{ci(d, 'f1')}</td>"
                         f"<td class=num>{pct(s['repo']['f1'])}</td><td class=num>{s['n_error']}</td><td class=num>{s['cost_usd']:.2f}</td></tr>")
    md += ["", "Paper (Liu, Stammbach, Henderson 2026, Table 2, same 390-example test split; ± = their reported half-widths):", "",
           "| Paper arm | P % | R % | F1 % |", "|---|---:|---:|---:|"]
    paper_html = []
    for label, p, r, f in PAPER:
        md.append(f"| {label} | {p[0]} ± {p[1]} | {r[0]} ± {r[1]} | {f[0]} ± {f[1]} |")
        paper_html.append(f"<tr><td>{html.escape(label)}</td><td class=num>{p[0]} ± {p[1]}</td><td class=num>{r[0]} ± {r[1]}</td><td class='num b'>{f[0]} ± {f[1]}</td></tr>")
    # per-type recall
    md += ["", "Per-error-type recall (% of required gold spans of that type matched; 'optional' spans excluded):", "",
           "| Arm | " + " | ".join(TYPE_LABEL[t] for t in L.TYPES) + " |", "|---|" + "---:|" * len(L.TYPES)]
    type_html = []
    for run_id, label, _ in ARMS:
        s = scores.get(run_id)
        if not s:
            continue
        bt = s["paper"]["recall_by_type"]
        cells = []
        for t in L.TYPES:
            v = bt.get(t)
            cells.append(f"{pct(v['recall'])} ({v['found']}/{v['gold']})" if v and v["gold"] else "–")
        md.append(f"| {label} | " + " | ".join(cells) + " |")
        type_html.append(f"<tr><td>{html.escape(label)}</td>" + "".join(f"<td class=num>{html.escape(c)}</td>" for c in cells) + "</tr>")
    for label, bt in PAPER_TYPES.items():
        md.append(f"| _paper: {label}_ | " + " | ".join(f"{bt[t]}" for t in L.TYPES) + " |")
        type_html.append(f"<tr class=paper><td>paper: {html.escape(label)}</td>" + "".join(f"<td class=num>{bt[t]}</td>" for t in L.TYPES) + "</tr>")
    # pilots / cost
    md += ["", "Pilots (20 train examples; measured tokens per example and the projection for 390 that gated each arm):", "",
           "| Pilot | n | F1 % | tokens in / out / cache-read / cache-write per ex. | cost $ | projected 390 $ |", "|---|---:|---:|---|---:|---:|"]
    for run_id, label in PILOTS:
        s = scores.get(run_id)
        if not s:
            continue
        q = con.execute("SELECT COUNT(*), AVG(tokens_in), AVG(tokens_out), AVG(cache_read), AVG(cache_write), SUM(cost_usd) FROM preds WHERE run_id=?", (run_id,)).fetchone()
        md.append(f"| {label} | {q[0]} | {pct(s['paper']['f1'])} | {q[1]:.0f} / {q[2]:.0f} / {q[3]:.0f} / {q[4]:.0f} | {q[5]:.2f} | {q[5] / max(q[0], 1) * 390:.2f} |")
    md_text = "\n".join(md) + "\n"
    open(os.path.join(L.RESULTS, "results_table.md"), "w").write(md_text)
    readme = os.path.join(L.HERE, "README.md")
    if os.path.exists(readme):
        t = open(readme).read()
        a, b = t.find("<!-- RESULTS -->"), t.find("<!-- /RESULTS -->")
        if a != -1 and b != -1:
            t = t[:a + len("<!-- RESULTS -->")] + "\n" + md_text + t[b:]
            open(readme, "w").write(t)
    # ---------------- html
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>LePhantomCite benchmark</title>
<style>
:root{{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1b;--mut:#6b6b66;--line:#e2e1dc;--acc:#2b5fb4;--code:#f0efea;--hl:#e4f3ea}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#161615;--card:#1f1f1d;--ink:#ecebe6;--mut:#a3a29b;--line:#34332f;--acc:#8fb3ff;--code:#2a2a27;--hl:#17301f}}}}
:root[data-theme=dark]{{--bg:#161615;--card:#1f1f1d;--ink:#ecebe6;--mut:#a3a29b;--line:#34332f;--acc:#8fb3ff;--code:#2a2a27;--hl:#17301f}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:20px 16px 80px}}h1{{font-size:22px;margin:0 0 4px}}h2{{font-size:18px;margin:28px 0 8px}}
.sub{{color:var(--mut);margin:0 0 16px}}.scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);border-radius:10px;background:var(--card)}}
table{{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}}th,td{{border-top:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}}
th{{color:var(--mut);font-weight:600;background:var(--card)}}td.num,th.num{{text-align:right;white-space:nowrap}}td.ci{{white-space:nowrap;color:var(--mut)}}td.b{{font-weight:700;background:var(--hl)}}
.note{{color:var(--mut);font-size:12px}}.mut{{color:var(--mut)}}tr.paper td{{color:var(--mut);font-style:italic}}
p,li{{max-width:900px}}code{{background:var(--code);padding:1px 4px;border-radius:4px}}a{{color:var(--acc)}}
</style></head><body><div class="wrap">
<h1>LePhantomCite: legal hallucination detection</h1>
<p class="sub">Syfert check_brief vs Claude Opus 5.5 vs local Gemma 4 E4B on the 390-example test split of the Princeton benchmark
(Liu, Stammbach, Henderson, "Who Checks the Citations?", arXiv 2606.21155v3). Generated {now}.</p>
<h2>Results (test split, paper matching rule)</h2>
<div class="scroll"><table><thead><tr><th>Arm</th><th class=num>n</th><th class=num>P %</th><th class=num>R %</th><th class=num>F1 %</th><th>P 95% CI</th><th>R 95% CI</th><th>F1 95% CI</th><th class=num>repo-rule F1</th><th class=num>errors</th><th class=num>cost $ (Claude Code: nominal, subscription)</th></tr></thead>
<tbody>{''.join(rows_html)}</tbody></table></div>
<h2>Paper's numbers (same test split, Table 2)</h2>
<div class="scroll"><table><thead><tr><th>Arm</th><th class=num>P %</th><th class=num>R %</th><th class=num>F1 %</th></tr></thead><tbody>{''.join(paper_html)}</tbody></table></div>
<h2>Recall by error type</h2>
<div class="scroll"><table><thead><tr><th>Arm</th>{''.join(f'<th class=num>{TYPE_LABEL[t]}</th>' for t in L.TYPES)}</tr></thead><tbody>{''.join(type_html)}</tbody></table></div>
<h2>Method</h2>
<ul>
<li><b>Data.</b> <code>eval.jsonl</code> from the HF dataset ai-law-society-lab/Legal_Phantom_Citation (390 excerpts: 300 from federal appellate briefs 2012–2021 with injected errors, 90 LLM-generated central holdings from Dahl et al.). Gold = <code>list_hallucinations</code> (span → type); 331 required spans + 22 "optional" spans.</li>
<li><b>Matching.</b> Strip + lower-case; a prediction hits a gold span when either is a substring of the other (plus the repo's ellipsis rule). Micro-averaged: precision = matching predictions / all predictions; recall = matched gold spans / gold spans. Optional spans count as hits when matched and are never misses (paper App. 8.4); "repo-rule F1" treats them as ordinary gold, as the public scorer's default does.</li>
<li><b>Syfert arm.</b> Each excerpt is sent once to the MCP tool <code>check_brief</code>; its findings are mapped deterministically to spans (strict: unresolved-with-fabrication-evidence, party-name mismatch, quote absent/misquote; broad: also any unresolved cite, near quotes, pinpoint-page failures, proposition mismatch). No model.</li>
<li><b>LLM arms.</b> Paper's non-agentic prompt (repo <code>max_steps=0</code> path), one sentence dropped (see README). Agentic arms add the paper's domain-knowledge block and a tool policy for the Syfert tools; the last turn is forced tool-free.</li>
<li><b>CIs.</b> 95% percentile bootstrap over examples (2000 resamples).</li>
</ul>
<h2>Caveats</h2>
<ul>
<li>A deterministic checker cannot see content misrepresentation (a real case cited for a holding it does not contain) or a wrong pincite that still falls inside the opinion; those are 131 + 55 of the 331 gold spans.</li>
<li><code>check_brief</code> only audits citations it extracts: short-form cites ("961 F.2d at 502") with no full cite in the excerpt and cites with an unknown reporter series ("830 N.W.4th 834", "475 F.6th 972") are skipped, so the injected non-existent citations built from fake reporter series are invisible to it.</li>
<li>Syfert's corpus is CourtListener-derived; 132 test citations are not on CourtListener and were left unaltered by the authors (all correct), so an "unresolved" finding is weak evidence there — the strict mapping ignores it, the broad mapping pays for it in precision.</li>
<li>The Dahl subset (90 examples) is 100% content-misrepresentation, which only the LLM arms can address.</li>
</ul>
<p class="mut">Raw per-example predictions, tool traces and usage: <code>~/projects/citebench/lephantom/results/lephantom.db</code> on xeric (tables runs, preds, calls) and <code>results/syfert_raw/*.json</code>.</p>
</div></body></html>"""
    open(os.path.join(L.RESULTS, "index.html"), "w").write(page)
    print("wrote results/results_table.md, results/index.html; README refreshed" if os.path.exists(readme) else "wrote results (no README yet)")


if __name__ == "__main__":
    main()
