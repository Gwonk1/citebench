#!/usr/bin/env python3
# usage: python3 -I prep_data.py   (reads labels_v1.1/*.jsonl, writes data/*.jsonl + id lists)
"""LePhantomCite data prep. Reads untrusted/dataset/{eval,aux_train}.jsonl (never imports anything from there),
assigns stable ids, writes data/test.jsonl (390), data/train.jsonl (910), data/pilot20.txt (20 train ids, 15 with
hallucinations / 5 clean), data/subset130.txt (130 test ids, stratified by source x has-hallucination, seed 20261016)."""
import json, os, random, collections
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "labels_v1.1")   # the v1.1 dataset files (eval.jsonl; aux_train.jsonl optional) — download from HF ai-law-society-lab/Legal_Phantom_Citation
OUT = os.path.join(HERE, "data")
os.makedirs(OUT, exist_ok=True)

def load(name, prefix):
    rows = []
    with open(os.path.join(SRC, name), encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            gold = r.get("list_hallucinations") or {}
            if isinstance(gold, list):  # defensive: list form -> untyped
                gold = {str(k): None for k in gold}
            rows.append({
                "id": f"{prefix}{i:03d}",
                "filename": r.get("filename"),
                "source": "dahl" if str(r.get("filename", "")).isdigit() else "brief",
                "text": r["text"],
                "gold": {str(k).strip(): (str(v).strip() if v else None) for k, v in gold.items() if str(k).strip()},
                "cite_types": r.get("list_hallucination_types") or {},
                "citations_in_segment": r.get("citations_in_segment") or [],
            })
    return rows

test = load("eval.jsonl", "t")
train = load("aux_train.jsonl", "r") if os.path.exists(os.path.join(SRC, "aux_train.jsonl")) else []
for name, rows in [("test.jsonl", test)] + ([("train.jsonl", train)] if train else []):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

# The shipped id lists (data/pilot20.txt, data/subset130.txt, data/train130.txt) were drawn with seed 20261016 over the FULL
# aux_train set; they are fixed so every arm uses the same examples. They are only regenerated when absent AND aux_train.jsonl is present.
if train and not os.path.exists(os.path.join(OUT, "subset130.txt")):
    pass
else:
    print("test", len(test), "train", len(train), "- id lists kept as shipped")
    raise SystemExit(0)
rng = random.Random(20261016)
# pilot: 20 train examples, 15 with >=1 required hallucination, 5 clean; mix of types
def required(r):
    return [k for k, v in r["gold"].items() if v != "optional"]
with_h = [r for r in train if required(r)]   # empty when aux_train.jsonl is absent (pilot20.txt is shipped)
clean = [r for r in train if not r["gold"]]
rng.shuffle(with_h); rng.shuffle(clean)
pilot = with_h[:15] + clean[:5]
if pilot:
    open(os.path.join(OUT, "pilot20.txt"), "w").write("\n".join(r["id"] for r in pilot) + "\n")

# subset130: stratified by (source, has_required_hallucination), proportional allocation, seed 20261016
strata = collections.defaultdict(list)
for r in test:
    strata[(r["source"], bool(required(r)))].append(r)
n_total = len(test); want = 130; picked = []
alloc = {k: round(want * len(v) / n_total) for k, v in strata.items()}
drift = want - sum(alloc.values())
# fix rounding drift on the largest stratum
big = max(alloc, key=lambda k: len(strata[k])); alloc[big] += drift
for k, rows in sorted(strata.items()):
    rows = sorted(rows, key=lambda r: r["id"]); rng.shuffle(rows)
    picked += rows[:alloc[k]]
picked.sort(key=lambda r: r["id"])
open(os.path.join(OUT, "subset130.txt"), "w").write("\n".join(r["id"] for r in picked) + "\n")

tc = collections.Counter(v for r in test for v in r["gold"].values())
print("test", len(test), "train", len(train), "pilot", len(pilot), "subset", len(picked))
print("test strata", {f"{k[0]}/{'halluc' if k[1] else 'clean'}": len(v) for k, v in strata.items()}, "alloc", {f"{k[0]}/{k[1]}": v for k, v in alloc.items()})
print("test gold types", dict(tc), "required spans", sum(len(required(r)) for r in test))
print("pilot types", dict(collections.Counter(v for r in pilot for v in r["gold"].values())))
