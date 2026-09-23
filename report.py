#!/usr/bin/env python3
# usage: python3 report.py [--db results/results.db] [--out results/report.md] [--include-mock] [--max-qid q0150]
"""Per-(model, arm) citebench metrics (SCHEMA.md) as markdown, plus bare -> mcp deltas per model.

Rates are micro-averaged: fabricated_rate = sum(n_fabricated)/sum(n_cites) over graded answers, etc.
gold_recall and abstain_rate are means over graded answers. Deltas (mcp - bare) are computed on the
questions graded in BOTH arms of the same model so the two arms see the same question set.
"""
import argparse
import datetime as dt
import json
import os

from cb_common import DB_PATH, ROOT, load_gold, open_db


def _para(r):
    """absent quotes that are accurate paraphrases in quotation marks (>= 60% in-order word overlap), g5+."""
    try:
        return (json.loads(r.get("check_brief_json") or "{}").get("_citebench") or {}).get("n_quote_paraphrase", 0) or 0
    except (ValueError, TypeError):
        return 0


def _cb(r, k):
    try:
        v = (json.loads(r.get("check_brief_json") or "{}").get("_citebench") or {}).get(k)
    except (ValueError, TypeError):
        v = None
    return len(v) if isinstance(v, list) else 0


def metrics(rows, gold=None):
    n = len(rows)
    if not n:
        return None
    gold = gold or {}
    bad = [r for r in rows if (gold.get(r["qid"]) or {}).get("gold_flag") in ("yellow", "red")]
    s = lambda k: sum(r[k] or 0 for r in rows)
    cites, ver = s("n_cites"), s("n_verified")
    return {
        "n": n, "cites": cites,
        "fabricated_rate": s("n_fabricated") / cites if cites else None,
        "fabricated_strict_rate": (s("n_fabricated") + s("n_unindexed")) / cites if cites else None,
        "misgrounded_rate": (s("n_name_mismatch") + s("n_quote_absent")) / cites if cites else None,
        "red_rate": s("n_red") / ver if ver else None,
        "gold_recall": s("gold_hit") / n,
        "abstain_rate": s("abstained") / n,
        "warned_rate": (sum(r.get("warned_treatment") or 0 for r in bad) / len(bad)) if bad else None,
        "court_propagated": sum(_cb(r, "court_propagated_miscite") for r in rows),
        "retracted": sum(_cb(r, "retracted_raw") for r in rows),
        "paraphrase_share": (sum(_para(r) for r in rows) / s("n_quote_absent")) if s("n_quote_absent") else None,
        "n_bad": len(bad),
    }


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def dpp(a, b):
    if a is None or b is None:
        return "n/a"
    return f"{100 * (b - a):+.1f} pp"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "report.md"))
    ap.add_argument("--include-mock", action="store_true", help="include dry-run (mock) runs")
    ap.add_argument("--max-qid", default=None, help="headline slice: only questions with qid <= this (e.g. q0150) so every run is scored on the same questions")
    a = ap.parse_args()
    con = open_db(a.db)
    con.row_factory = __import__("sqlite3").Row

    gold = load_gold(con)
    runs = con.execute("SELECT * FROM runs ORDER BY run_id").fetchall()
    per = {}
    for run in runs:
        cfg = json.loads(run["config_json"] or "{}")
        mkey = cfg.get("model_key", run["model"])
        if (mkey == "mock" or cfg.get("dry_run")) and not a.include_mock:
            continue
        ans = con.execute("SELECT * FROM answers WHERE run_id=?", (run["run_id"],)).fetchall()
        grades = {r["qid"]: dict(r) for r in con.execute("SELECT * FROM grades WHERE run_id=?", (run["run_id"],))}
        if a.max_qid:
            ans = [x for x in ans if x["qid"] <= a.max_qid]
            grades = {q: g for q, g in grades.items() if q <= a.max_qid}
        tool_calls = [len(json.loads(x["tool_calls_json"] or "[]")) for x in ans]
        gv = sorted({g.get("grader_version") or "unstamped (pre-g3)" for g in grades.values()})
        per[run["run_id"]] = {
            "model": mkey, "arm": run["arm"], "tag": run["run_id"].rsplit(":", 1)[-1],
            "answers": len(ans), "errors": sum(1 for x in ans if x["error"]),
            "cost": sum(x["cost_usd"] or 0 for x in ans),
            "lat": (sum(x["latency_s"] or 0 for x in ans) / len(ans)) if ans else 0,
            "tools": (sum(tool_calls) / len(tool_calls)) if tool_calls else 0,
            "grades": grades, "grader_versions": gv,
        }

    lines = [f"# citebench report", "", f"generated {dt.datetime.now().isoformat(timespec='seconds')} from `{a.db}`"
             + (f" — HEADLINE SLICE: questions <= {a.max_qid} only (same questions for every run)" if a.max_qid else ""), ""]
    hdr = ("| model | arm | run | answered | errors | graded | cites | fabricated_rate | fabricated_strict_rate | court_propagated | retracted | misgrounded_rate | "
           "paraphrase_share | red_rate | gold_recall | abstain_rate | warned_rate (bad-law n) | avg tool calls | avg latency s | cost $ |")
    lines += ["## Metrics per (model, arm)", "", hdr, "|" + "---|" * (hdr.count("|") - 1)]
    for rid, p in sorted(per.items(), key=lambda kv: (kv[1]["model"], kv[1]["tag"], kv[1]["arm"])):
        m = metrics(list(p["grades"].values()), gold)
        if m is None:
            m = {"n": 0, "cites": 0, "fabricated_rate": None, "fabricated_strict_rate": None, "misgrounded_rate": None,
                 "red_rate": None, "gold_recall": None, "abstain_rate": None, "warned_rate": None, "n_bad": 0,
                 "paraphrase_share": None, "court_propagated": 0, "retracted": 0}
        lines.append(f"| {p['model']} | {p['arm']} | {rid} | {p['answers']} | {p['errors']} | {m['n']} | "
                     f"{m['cites']} | {pct(m['fabricated_rate'])} | {pct(m['fabricated_strict_rate'])} | {m.get('court_propagated', 0)} | "
                     f"{m.get('retracted', 0)} | {pct(m['misgrounded_rate'])} | "
                     f"{pct(m['paraphrase_share'])} | "
                     f"{pct(m['red_rate'])} | {pct(m['gold_recall'])} | {pct(m['abstain_rate'])} | "
                     f"{pct(m['warned_rate'])} ({m['n_bad']}) | "
                     f"{p['tools']:.1f} | {p['lat']:.1f} | {p['cost']:.4f} |")

    allv = sorted({v for p in per.values() for v in p["grader_versions"]})
    lines += ["", "Grader version(s): " + ", ".join(f"`{v}`" for v in allv)
              + ("" if len(allv) <= 1 else "  **MIXED: regrade with `python3 grade.py --regrade` before comparing runs**")]
    for rid, p in sorted(per.items()):
        if len(allv) > 1:
            lines.append(f"- {rid}: {', '.join(p['grader_versions']) or 'ungraded'}")
    # deltas
    lines += ["", "## bare -> mcp delta (mcp minus bare, on questions graded in both arms)", "",
              "| model | tag | common q | Δ fabricated_rate | Δ misgrounded_rate | Δ red_rate | Δ gold_recall | Δ abstain_rate | Δ warned_rate |",
              "|---|---|---|---|---|---|---|---|---|"]
    pairs = {}
    for rid, p in per.items():
        pairs.setdefault((p["model"], p["tag"]), {})[p["arm"]] = p
    any_pair = False
    for (model, tag), arms in sorted(pairs.items()):
        if "bare" not in arms or "mcp" not in arms:
            continue
        common = set(arms["bare"]["grades"]) & set(arms["mcp"]["grades"])
        if not common:
            continue
        any_pair = True
        mb = metrics([arms["bare"]["grades"][q] for q in common], gold)
        mm = metrics([arms["mcp"]["grades"][q] for q in common], gold)
        lines.append(f"| {model} | {tag} | {len(common)} | "
                     + " | ".join(dpp(mb[k], mm[k]) for k in
                                  ("fabricated_rate", "misgrounded_rate", "red_rate", "gold_recall", "abstain_rate", "warned_rate"))
                     + " |")
    if not any_pair:
        lines.append("| (no model has both arms graded yet) | | | | | | | | |")
    lines += ["", "Definitions: fabricated_rate = n_fabricated/n_cites (headline: unresolved cites that reconcile.py "
              "could NOT match to a real, not-yet-indexed case); fabricated_strict_rate = (n_fabricated + n_unindexed)/n_cites "
              "(every cite the reporter index cannot resolve, for transparency); misgrounded_rate = (n_name_mismatch + "
              "n_quote_absent)/n_cites; court_propagated = fabricated cites that are real cases "
              "miscited with a wrong volume/page that >= 2 other courts' opinions repeat (g6); retracted = cites the "
              "model withdrew in the same answer, excluded from n_cites (g6); paraphrase_share = share of absent quotes that are accurate paraphrases "
              "put in quotation marks (>= 60% of the words in order; the rest are fabricated wording), graded "
              "g5+ only; red_rate = n_red/n_verified; gold_recall = mean(gold_hit); "
              "abstain_rate = mean(abstained); warned_rate = mean(warned_treatment) over questions whose gold_flag "
              "is yellow/red only (count in parentheses). Rates are pooled over answers. See grade.py docstring for how "
              "check_brief output maps to each count."]
    md = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write(md)
    print(md)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
