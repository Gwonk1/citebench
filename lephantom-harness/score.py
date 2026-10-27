#!/usr/bin/env python3
# usage: python3 score.py [--db PATH] [--run RUN_ID ...] [--boot 2000] [--json OUT] [--split train|test]
"""Score every run in results/lephantom.db (or the named runs) with the paper's rule (see lp_common docstring).
Prints micro P/R/F1 with 95% bootstrap CIs over examples (resample examples with replacement, recompute micro
metrics, 2.5/97.5 percentiles), per-type recall (type of each gold span; 'optional' never counted), the repo-default
variant (optional spans as ordinary gold), and error/parse counts. Examples with a stored error count as empty
predictions (they are listed). Writes results/scores.json."""
import argparse, json, os, random, collections
import lp_common as L
RAW_SPANS = False


def aggregate(scored):
    a = [0, 0, 0, 0]
    for s in scored:
        a = [x + y for x, y in zip(a, (s["found"], s["gold"], s["tp"], s["pred"]))]
    return L.prf(*a), a


def bootstrap(scored, n=2000, seed=20261016):
    rng = random.Random(seed)
    out = {"p": [], "r": [], "f1": []}
    m = len(scored)
    for _ in range(n):
        sample = [scored[rng.randrange(m)] for _ in range(m)]
        (p, r, f), _ = aggregate(sample)
        out["p"].append(p); out["r"].append(r); out["f1"].append(f)
    ci = {}
    for k, v in out.items():
        v.sort()
        ci[k] = (v[int(0.025 * n)], v[int(0.975 * n) - 1])
    return ci


def score_run(con, run_id, rows_by_id, boot):
    preds = {}
    errors = []
    parse = collections.Counter()
    cost = tin = tout = 0.0
    for ex_id, pj, ps, err, c, ti, to in con.execute(
            "SELECT ex_id, predicted_json, parse_status, error, cost_usd, tokens_in, tokens_out FROM preds WHERE run_id=?", (run_id,)):
        if ex_id not in rows_by_id:
            continue
        preds[ex_id] = [L.anchor_span(x, rows_by_id[ex_id]["text"]) for x in (json.loads(pj) if pj else [])] if not RAW_SPANS else (json.loads(pj) if pj else [])
        parse[ps or ("error" if err else "?")] += 1
        if err:
            errors.append(ex_id)
        cost += c or 0; tin += ti or 0; tout += to or 0
    ids = sorted(preds)
    if not ids:
        return None
    res = {"run_id": run_id, "n": len(ids), "n_error": len(errors), "errors": errors[:50], "parse": dict(parse),
           "cost_usd": round(cost, 4), "tokens_in": int(tin), "tokens_out": int(tout)}
    for rule in ("paper", "repo"):
        scored = [L.score_example(rows_by_id[i]["gold"], preds[i], rule) for i in ids]
        (p, r, f), a = aggregate(scored)
        d = {"precision": p, "recall": r, "f1": f, "counts": dict(zip(("found", "gold", "tp", "pred"), a))}
        if rule == "paper":
            d["ci95"] = bootstrap(scored, boot)
            bt = collections.defaultdict(lambda: [0, 0])
            for s in scored:
                for t, (f_, g_) in s["by_type"].items():
                    bt[t][0] += f_; bt[t][1] += g_
            d["recall_by_type"] = {t: {"found": v[0], "gold": v[1], "recall": (v[0] / v[1] if v[1] else None)}
                                   for t, v in sorted(bt.items())}
            # per-source
            for src in ("brief", "dahl"):
                sub = [s for i, s in zip(ids, scored) if rows_by_id[i]["source"] == src]
                if sub:
                    (sp, sr, sf), sa = aggregate(sub)
                    d[f"{src}"] = {"n": len(sub), "precision": sp, "recall": sr, "f1": sf}
            # clean-example false positives
            clean = [i for i in ids if not any(v != "optional" for v in rows_by_id[i]["gold"].values())]
            d["clean_examples"] = {"n": len(clean), "with_any_prediction": sum(1 for i in clean if preds[i]),
                                   "predictions": sum(len(preds[i]) for i in clean)}
        res[rule] = d
    return res


def fmt_pct(x):
    return f"{100 * x:5.1f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=L.DB_PATH)
    ap.add_argument("--run", nargs="*")
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--json", default=os.path.join(L.RESULTS, "scores.json"))
    ap.add_argument("--raw-spans", action="store_true", help="score the model's strings as written (no anchor_span normalisation)")
    ap.add_argument("--split", choices=("test", "train"), help="load ONLY this split's gold (train = development; never tune on test)")
    a = ap.parse_args()
    global RAW_SPANS
    RAW_SPANS = a.raw_spans
    con = L.open_db(a.db)
    rows = {}
    for sp in ((a.split,) if a.split else ("test", "train")):
        rows.update({r["id"]: r for r in L.load_split(sp)})
    runs = a.run or [r[0] for r in con.execute("SELECT run_id FROM runs ORDER BY started_ts")]
    out = []
    print(f"{'run':46} {'n':>4} {'err':>3} | {'P':>5} {'R':>5} {'F1':>5} | {'P ci':>13} {'R ci':>13} {'F1 ci':>13} | repo F1 | $")
    for run_id in runs:
        res = score_run(con, run_id, rows, a.boot)
        if not res:
            continue
        out.append(res)
        d = res["paper"]; ci = d["ci95"]
        print(f"{run_id:46} {res['n']:4} {res['n_error']:3} | {fmt_pct(d['precision'])} {fmt_pct(d['recall'])} {fmt_pct(d['f1'])} | "
              f"{fmt_pct(ci['p'][0])}-{fmt_pct(ci['p'][1])} {fmt_pct(ci['r'][0])}-{fmt_pct(ci['r'][1])} {fmt_pct(ci['f1'][0])}-{fmt_pct(ci['f1'][1])} | "
              f"{fmt_pct(res['repo']['f1'])} | {res['cost_usd']:.2f}")
        print("   by type: " + "  ".join(f"{t}={fmt_pct(v['recall']).strip()}% ({v['found']}/{v['gold']})"
                                        for t, v in d["recall_by_type"].items() if v["gold"]))
        print(f"   clean examples: {d['clean_examples']}  parse: {res['parse']}  brief/dahl F1: "
              f"{fmt_pct(d.get('brief', {}).get('f1', 0))}/{fmt_pct(d.get('dahl', {}).get('f1', 0))}")
    os.makedirs(os.path.dirname(a.json), exist_ok=True)
    json.dump(out, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
