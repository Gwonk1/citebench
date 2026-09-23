#!/usr/bin/env python3
# usage: ssh cloud-ts cat /var/lib/syfert/citebench-audit/verdicts.jsonl | python3 audit/score.py
"""Grader precision on the 50 quote verdicts (+ the 10 name verdicts) with 95% Wilson intervals.
Latest line per id wins; 'unsure' is reported and excluded from the denominator."""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
items = {i["id"]: i for i in json.load(open(os.path.join(HERE, "packet.json")))["items"]}
latest = {}
for line in sys.stdin:
    line = line.strip()
    if line:
        r = json.loads(line)
        if r["verdict"] == "clear":
            latest.pop(r["id"], None)
        else:
            latest[r["id"]] = r["verdict"]


def wilson(k, n, z=1.96):
    if not n:
        return (float("nan"),) * 2
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


for label, pred in (("quote verdicts (35 absent + 15 found)", lambda i: i["section"] == "quote"),
                    ("  absent only", lambda i: i["stratum"] == "absent"),
                    ("  found only", lambda i: i["stratum"] == "found"),
                    ("name mismatch (10)", lambda i: i["section"] == "name")):
    ids = [k for k, i in items.items() if pred(i)]
    v = [latest.get(k) for k in ids]
    right, wrong, unsure, todo = v.count("right"), v.count("wrong"), v.count("unsure"), v.count(None)
    n = right + wrong
    lo, hi = wilson(right, n)
    print(f"{label}: right {right} / wrong {wrong} / unsure {unsure} / not yet judged {todo}"
          + (f"  precision {right / n:.1%} (95% Wilson {lo:.1%} to {hi:.1%})" if n else ""))
