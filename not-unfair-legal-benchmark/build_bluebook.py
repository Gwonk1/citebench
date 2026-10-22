# Items for opinion-sourced cites, Florida DCA parentheticals, and WL/LEXIS
# offered next to an official reporter. usage: python3 build_bluebook.py
import json
import os
import sqlite3
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
META = "/home/graham/projects/courtlistener/pkg/caselaw_meta.db"
CITE_ADDS = "/home/graham/projects/caselaw-tools/gapfill/gapfill_intake/cite_adds.tsv"
DCA = "/home/graham/projects/pipeline/out/fl_dca_districts.db"
ORD = {1: "1st", 2: "2d", 3: "3d", 4: "4th", 5: "5th", 6: "6th"}
VENDOR = ("WL",)  # plus any reporter ending in LEXIS

meta = sqlite3.connect(META)
meta.execute("PRAGMA query_only=ON")


def take(rows, n):
    rows = list(rows)
    if len(rows) <= n:
        return rows
    step = len(rows) / n
    return [rows[int(i * step)] for i in range(n)]


def case_row(cid):
    return meta.execute(
        "SELECT case_name, date_filed, docket_number, court_id FROM cases WHERE cluster_id=?",
        (int(cid),),
    ).fetchone()


def citations_of(cid):
    return meta.execute(
        "SELECT volume, reporter, page, type FROM citations WHERE cluster_id=?",
        (int(cid),),
    ).fetchall()


def cite_of(vol, rep, page):
    return f"{vol} {rep} {page}"


def is_vendor(rep):
    return rep == "WL" or (rep or "").endswith("LEXIS")


def is_reporter(rep, page):
    return bool(rep) and not is_vendor(rep) and str(page).isdigit()


items = []

# Cites recovered from citing opinions (citefill_name_year), one per cluster,
# and not already a different cite on the cluster.
by = defaultdict(list)
with open(CITE_ADDS) as f:
    f.readline()
    for line in f:
        p = line.rstrip("\n").split("\t")
        if len(p) < 7 or p[0] != "add" or p[6] != "citefill_name_year":
            continue
        by[int(p[4])].append((p[1], p[2], p[3]))
solos = sorted((cid, c[0]) for cid, c in by.items() if len(c) == 1)
opinion = []
for cid, (vol, rep, page) in take(solos, 60):
    have = citations_of(cid)
    key = (str(vol), rep, str(page))
    others = [h for h in have if (str(h[0]), h[1], str(h[2])) != key]
    if others:
        continue
    name = case_row(cid)
    if not name or not name[0]:
        continue
    opinion.append((cid, vol, rep, page, name[0], name[1] or ""))
    if len(opinion) == 8:
        break
for i, (cid, vol, rep, page, name, filed) in enumerate(opinion, 1):
    cite = cite_of(vol, rep, page)
    items.append({
        "id": f"op-{i:02d}",
        "class": "opinion_cite",
        "tool": "analyze_citations",
        "text": f"{name}, {cite}.",
        "gold": {
            "cluster_id": cid, "cite": cite, "case_name": name, "date_filed": filed,
            "source": "cite_adds citefill_name_year, only cite, from a citing opinion",
        },
    })

# One Florida DCA case per district, twice, with a reporter cite.
dca = sqlite3.connect(DCA)
for dist in range(1, 7):
    found = []
    offset = 0
    while len(found) < 2 and offset < 400:
        rows = dca.execute(
            "SELECT cluster_id FROM fl_dca_districts WHERE district=? LIMIT 40 OFFSET ?",
            (dist, offset),
        ).fetchall()
        if not rows:
            break
        offset += 40
        for (cid,) in rows:
            cites = [c for c in citations_of(cid) if is_reporter(c[1], c[2])]
            if not cites:
                continue
            name = case_row(cid)
            if not name or not name[0]:
                continue
            vol, rep, page = cites[0][:3]
            found.append((cid, name[0], cite_of(vol, rep, page), name[2] or ""))
            if len(found) == 2:
                break
    parenthetical = f"Fla. {ORD[dist]} DCA"
    for j, (cid, name, cite, docket) in enumerate(found, 1):
        items.append({
            "id": f"dca-{dist}-{j}",
            "class": "bluebook_court",
            "tool": "fldca",
            "text": f"{name}, {cite} ({parenthetical}).",
            "cluster_id": cid,
            "gold": {
                "cluster_id": cid, "cite": cite, "case_name": name,
                "district": dist, "parenthetical": parenthetical,
                "docket_number": docket,
                "source": "fl_dca_districts.db; correct form is the numbered DCA, not Fla. Dist. Ct. App., and not 3rd",
            },
        })

# Official reporter plus a WL or LEXIS cite on the same cluster.
vendor_rows = []
for year, reporter in (("2018", "WL"), ("2016", "WL"), ("2019", "Fla. App. LEXIS"), ("2015", "U.S. App. LEXIS")):
    hits = meta.execute(
        "SELECT cluster_id, volume, reporter, page FROM citations WHERE volume=? AND reporter=? LIMIT 25",
        (year, reporter),
    ).fetchall()
    for cid, vvol, vrep, vpage in hits:
        official = [c for c in citations_of(cid) if is_reporter(c[1], c[2])]
        if not official:
            continue
        name = case_row(cid)
        if not name or not name[0]:
            continue
        vol, rep, page = official[0][:3]
        vendor_rows.append((cid, name[0], cite_of(vol, rep, page), cite_of(vvol, vrep, vpage)))
        if len(vendor_rows) >= 8:
            break
    if len(vendor_rows) >= 8:
        break
seen = set()
n = 0
for cid, name, official, vendor in vendor_rows:
    if cid in seen:
        continue
    seen.add(cid)
    n += 1
    items.append({
        "id": f"vend-{n:02d}",
        "class": "vendor_when_official",
        "tool": "analyze_citations",
        "text": f"{name}, {official}.",
        "gold": {
            "cluster_id": cid, "official": official, "vendor": vendor, "case_name": name,
            "source": "caselaw_meta citations: reporter and WL/LEXIS on the same cluster",
        },
    })
    if n == 8:
        break

out = os.path.join(HERE, "items", "bluebook.jsonl")
with open(out, "w") as f:
    for row in items:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
from collections import Counter
print("wrote", len(items), "->", out)
print(Counter(r["class"] for r in items))
