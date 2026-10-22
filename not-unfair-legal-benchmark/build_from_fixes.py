# Build a wave of CourtListener-MCP items from the fix ledgers on this machine.
# usage: python3 build_from_fixes.py
# Writes items/from_fixes.jsonl. Does not call the network.
import json
import os
import sqlite3
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
META = "/home/graham/projects/courtlistener/pkg/caselaw_meta.db"
CITE_ADDS = "/home/graham/projects/caselaw-tools/gapfill/gapfill_intake/cite_adds.tsv"
DEMOTE = "/home/graham/projects/caselaw-tools/leaglefix_20261015/out/demote_delta_run_leaglefix_fl_given_20261015.tsv"
SUPER = "/home/graham/projects/caselaw-tools/cluster_superseded_work/cluster_superseded.db"
TREAT = "/home/graham/projects/treatment_flags_all.db"
PUB = "/home/graham/projects/courtlistener/pub_status_work/pub_status.db"
MISCITE = "/home/graham/projects/caselaw-tools/miscited/overlay/miscite_overlay.db"
ALIASES = "/home/graham/projects/courtlistener/cite_aliases_curated.db"
HYGIENE = "/home/graham/projects/caselaw-tools/text_hygiene/bake/rollback_run_2026-09-30.db"
N = 8

meta = sqlite3.connect(META)
meta.execute("PRAGMA query_only=ON")


def cite_of(vol, rep, page):
    return f"{vol} {rep} {page}"


def case_row(cluster_id):
    return meta.execute(
        "SELECT case_name, date_filed FROM cases WHERE cluster_id=?",
        (int(cluster_id),),
    ).fetchone()


def citations_of(cluster_id):
    return meta.execute(
        "SELECT volume, reporter, page FROM citations WHERE cluster_id=?",
        (int(cluster_id),),
    ).fetchall()


def first_reporter(cluster_id):
    rows = [
        r for r in citations_of(cluster_id)
        if r[1] and r[0] and r[2] and r[2].isdigit() and r[1] not in ("WL", "U.S. LEXIS")
    ]
    return rows[0] if rows else None


def opinion_id(cluster_id):
    rows = meta.execute(
        "SELECT id, type FROM opinions_meta WHERE cluster_id=? ORDER BY id",
        (int(cluster_id),),
    ).fetchall()
    for oid, typ in rows:
        if typ and "combined" in str(typ):
            return oid
    return rows[0][0] if rows else None


def take(rows, n):
    rows = list(rows)
    if len(rows) <= n:
        return rows
    step = len(rows) / n
    return [rows[int(i * step)] for i in range(n)]


def item(iid, klass, text, gold, tool="analyze_citations", **extra):
    row = {"id": iid, "class": klass, "tool": tool, "text": text, "gold": gold}
    row.update(extra)
    return row


items = []

# 1. Coverage: a cluster whose only added cite is one Leagle volume cite,
# and the caselaw meta citation list has nothing else.
solos = []
by = {}
with open(CITE_ADDS) as f:
    f.readline()
    for line in f:
        p = line.rstrip("\n").split("\t")
        if len(p) < 7 or p[0] != "add" or p[6] != "leagle_volume":
            continue
        by.setdefault(p[4], []).append((p[1], p[2], p[3]))
for cid, cites in by.items():
    if len(cites) == 1:
        solos.append((int(cid),) + cites[0])
solos.sort()
coverage = []
for cid, vol, rep, page in take(solos, 80):
    have = citations_of(cid)
    leagle = (str(vol), rep, str(page))
    others = [h for h in have if (str(h[0]), h[1], str(h[2])) != leagle]
    if others:
        continue
    name = case_row(cid)
    if not name or not name[0]:
        continue
    coverage.append((cid, vol, rep, page, name[0], name[1] or ""))
    if len(coverage) == N:
        break
for i, (cid, vol, rep, page, name, filed) in enumerate(coverage, 1):
    cite = cite_of(vol, rep, page)
    items.append(item(
        f"c1-{i:02d}", "coverage",
        f"{name}, {cite}.",
        {"cluster_id": cid, "cite": cite, "case_name": name, "date_filed": filed,
         "source": "cite_adds leagle_volume, only cite on the cluster"},
    ))

# 2. Wrong cites we took off the index (Leagle given-name mismatches).
demoted = []
with open(DEMOTE) as f:
    f.readline()
    for line in f:
        p = line.rstrip("\n").split("\t")
        if len(p) < 5 or p[0] != "del":
            continue
        demoted.append((p[1], p[2], p[3], int(p[4])))
for i, (vol, rep, page, cid) in enumerate(take(demoted, N), 1):
    name = case_row(cid)
    cname = name[0] if name else ""
    cite = cite_of(vol, rep, page)
    items.append(item(
        f"c2-{i:02d}", "wrong_index",
        f"{cname}, {cite}.",
        {"removed_from_cluster": cid, "cite": cite, "case_name": cname,
         "source": "leaglefix given-name demote 2026-10-15"},
    ))

# 3. Twin clusters that share a reporter cite.
sup = sqlite3.connect(SUPER)
pairs = sup.execute(
    "SELECT cluster_id, superseded_by, reason FROM cluster_superseded LIMIT 400"
).fetchall()
twins = []
for cid, other, reason in pairs:
    a = {(str(v), r, str(p)) for v, r, p in citations_of(cid)}
    b = {(str(v), r, str(p)) for v, r, p in citations_of(other)}
    shared = [t for t in a & b if t[2].isdigit()]
    if not shared:
        continue
    vol, rep, page = shared[0]
    name = case_row(cid)
    twins.append((cid, other, cite_of(vol, rep, page), name[0] if name else "", reason or ""))
    if len(twins) == N:
        break
for i, (cid, other, cite, name, reason) in enumerate(twins, 1):
    items.append(item(
        f"c3-{i:02d}", "twin",
        f"{name}, {cite}.",
        {"cluster_id": cid, "other_cluster_id": other, "cite": cite,
         "case_name": name, "reason": reason, "source": "cluster_superseded.db"},
    ))

# 4. Treatment: red flags. The tool has no treatment field.
treat = sqlite3.connect(TREAT)
reds = treat.execute(
    "SELECT cluster_id, strongest_signal, strongest_citing_case, strongest_citing_date "
    "FROM treatment_summary WHERE flag_color='red' LIMIT 60"
).fetchall()
treatment = []
for cid, signal, citer, cdate in reds:
    repc = first_reporter(cid)
    name = case_row(cid)
    if not repc or not name:
        continue
    treatment.append((cid, cite_of(*repc), name[0], signal or "", citer or "", cdate or ""))
    if len(treatment) == N:
        break
for i, (cid, cite, name, signal, citer, cdate) in enumerate(treatment, 1):
    items.append(item(
        f"c4-{i:02d}", "treatment",
        f"{name}, {cite}.",
        {"cluster_id": cid, "cite": cite, "case_name": name, "signal": signal,
         "citing_case": citer, "citing_date": cdate, "source": "treatment_flags_all.db red"},
    ))

# 4b. Unpublished that we overrode from CourtListener's Published label.
pub = sqlite3.connect(PUB)
unpubs = pub.execute(
    "SELECT cluster_id, evidence FROM pub_status "
    "WHERE status='Unpublished' AND status_source='inferred_text' LIMIT 40"
).fetchall()
unpublished = []
for cid, evidence in unpubs:
    repc = first_reporter(cid)
    name = case_row(cid)
    if not repc or not name:
        continue
    unpublished.append((cid, cite_of(*repc), name[0], evidence or ""))
    if len(unpublished) == N:
        break
for i, (cid, cite, name, evidence) in enumerate(unpublished, 1):
    items.append(item(
        f"c4b-{i:02d}", "treatment",
        f"{name}, {cite}.",
        {"cluster_id": cid, "cite": cite, "case_name": name, "evidence": evidence,
         "source": "pub_status inferred_text override of CourtListener Published"},
    ))
    items.append(item(
        f"c4b-{i:02d}-status", "treatment",
        "",
        {"cluster_id": cid, "expect_cl_label": "Published", "our_label": "Unpublished"},
        tool="cluster",
        cluster_id=cid,
    ))

# 5. Pagination: a printed cite that is an interior page of the real cite.
misc = sqlite3.connect(MISCITE)
pins = misc.execute(
    "SELECT printed, real_cite, case_name FROM fix WHERE why='pin' AND printed!=real_cite"
).fetchall()
for i, (printed, real, name) in enumerate(take(pins, N), 1):
    items.append(item(
        f"c5-{i:02d}", "pagination",
        f"{name}, {printed}.",
        {"printed": printed, "real_cite": real, "case_name": name,
         "source": "miscite_overlay why=pin"},
    ))

# 6. Westlaw / LEXIS aliases we accepted or promoted.
al = sqlite3.connect(ALIASES)
aliases = al.execute(
    "SELECT alias_cite, cluster_id, verdict FROM decisions "
    "WHERE alias_cite LIKE '%WL%' OR alias_cite LIKE '%LEXIS%'"
).fetchall()
aliases += al.execute(
    "SELECT alias_cite, cluster_id, tier FROM claim_promotions "
    "WHERE alias_cite LIKE '%WL%' OR alias_cite LIKE '%LEXIS%'"
).fetchall()
seen = set()
vendor = []
for alias, cid, how in aliases:
    if alias in seen:
        continue
    seen.add(alias)
    name = case_row(cid)
    vendor.append((alias, cid, name[0] if name else "", how))
for i, (alias, cid, name, how) in enumerate(vendor, 1):
    items.append(item(
        f"c6-{i:02d}", "vendor",
        f"{name}, {alias}.",
        {"alias": alias, "cluster_id": cid, "case_name": name, "how": how,
         "source": "cite_aliases_curated.db"},
    ))

# 8. Misprint vs fabrication: a one-edit printed cite, real cite known.
typos = misc.execute(
    "SELECT printed, real_cite, case_name FROM fix WHERE why='typo' AND printed!=real_cite"
).fetchall()
for i, (printed, real, name) in enumerate(take(typos, N), 1):
    items.append(item(
        f"c8-{i:02d}", "misprint",
        f"{name}, {printed}.",
        {"printed": printed, "real_cite": real, "case_name": name,
         "source": "miscite_overlay why=typo"},
    ))

# 9. Caption form: the case is In re; the passage says Matter of.
inre = misc.execute(
    "SELECT case_name, real_cite FROM fix WHERE case_name LIKE 'In re %' "
    "AND real_cite!='' AND real_cite NOT LIKE '%WL%'"
).fetchall()
# one row per real cite
dedup = []
seen_c = set()
for name, real in inre:
    if real in seen_c:
        continue
    seen_c.add(real)
    dedup.append((name, real))
for i, (name, real) in enumerate(take(dedup, N), 1):
    rest = name[6:].strip() if name.lower().startswith("in re ") else name
    items.append(item(
        f"c9-{i:02d}", "caption",
        f"Matter of {rest}, {real}.",
        {"canonical_name": name, "sent_as": f"Matter of {rest}", "cite": real,
         "source": "miscite_overlay In re rows, Matter of rewrite"},
    ))

# 10. Garbled text we repaired. A short span from the pre-fix opinion.
hyg = sqlite3.connect(HYGIENE)
tells = ("oFTHE", "oF THE", "tbe ", "wliich", "corut")
ocr = []
for cid, blob in hyg.execute(
    "SELECT cluster_id, before FROM changes WHERE length(before)>800 LIMIT 2500"
):
    try:
        text = zlib.decompress(blob, -15).decode("utf-8", "replace")
    except Exception:
        continue
    hit = next((t for t in tells if t in text), None)
    if not hit:
        continue
    at = text.find(hit)
    window = " ".join(text[max(0, at - 30):at + 50].split())
    if len(window) < 25:
        continue
    oid = opinion_id(cid)
    if not oid:
        continue
    ocr.append((cid, oid, window, hit))
    if len(ocr) == N:
        break
for i, (cid, oid, window, hit) in enumerate(ocr, 1):
    items.append(item(
        f"c10-{i:02d}", "ocr",
        "",
        {"cluster_id": cid, "tell": hit, "source": "text_hygiene rollback before-blob"},
        tool="opinion",
        opinion_id=oid,
        cluster_id=cid,
        snippet=window,
    ))

out = os.path.join(HERE, "items", "from_fixes.jsonl")
with open(out, "w") as f:
    for row in items:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
from collections import Counter
print("wrote", len(items), "->", out)
print(Counter(r["class"] for r in items))
