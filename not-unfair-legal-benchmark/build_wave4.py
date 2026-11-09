# Build the v1.4 CANDIDATE wave ("wave 4") from the 2026-11-09 corrections: two decisions on one first page (new class
# `samepage`, ids pg-*) and New York Appellate Division cites filed as "N.Y.2d" (new class `nyseries`, ids ny-*), plus
# matching controls.
#
# usage:
#   python3 build_wave4.py --pool                      # draw the move, stray, NY and control pools (offline)
#   python3 build_wave4.py --evidence --network        # Syfert MCP check_citation + search_cases per pool row
#   python3 build_wave4.py --cl --network [--max 150]  # raw CourtListener analyze_citations per candidate item
#   python3 build_wave4.py                             # offline: build items from what is on disk
#
# No network call is made unless --network is given. Every network reply is saved under OUT; the offline build reads
# only those files, the lane ledgers and caselaw_meta.db (opened read-only; dated 2026-11-06, before these fixes, so it
# holds CourtListener's own numbers). Writes items/wave4.jsonl and OUT/{pool_*.jsonl,evidence_*.jsonl,pre_cl.jsonl,
# drops.jsonl,spares.jsonl,cl_verdicts.jsonl,summary.json}. It never touches items/tasks.jsonl, VERSION or CHANGELOG.md.
#
# Sources (read-only):
#   move   PAGE195/out/decisions.json  act=move-page: CourtListener files the case at a page that is another case's first
#                                       page; citing opinions print a different page 3+ times and that page is free.
#   stray  PRIM203 out_sv.json (copied to OUT/src/prim203_out_sv.json): CourtListener lists a second, stray first page
#                                       beside the case's own page in the same volume, and lists the stray FIRST; the stray
#                                       is another decision's first page (now_owner).
#          PAGE195/out/decisions.json  act=drop, "this row is a stray": same shape (the case already holds the right page).
#   ny     XREP204/out/ny_class.json   k=RELABEL_free: an Appellate Division cite filed as "<vol> N.Y.2d <page>" with
#                                       vol 232-980 (N.Y.2d ended at vol 100); it is N.Y.S.2d, and no other case holds
#                                       that N.Y.S.2d key. XREP204/out/ny_ev.json: citing-event counts per row id.
#
# Evidence uses build_regional.py's gather / evaluate / build_item code unchanged (same standard: two or more citing
# opinions that print the cite in the 160 characters after a party word of the name, none printing the old cite with the
# name, the decision year inside the volume's span, no other cluster at the printed cite).
import argparse
import json
import os
import re
from collections import Counter

import build_regional as br
import grade

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "20261109-wave4")
LANES = br.LANES
DECISIONS = os.path.join(LANES, "PAGE195/out/decisions.json")
PRIM = os.path.join(OUT, "src", "prim203_out_sv.json")
NY_CLASS = os.path.join(LANES, "XREP204/out/ny_class.json")
NY_EV = os.path.join(LANES, "XREP204/out/ny_ev.json")
ITEMS_OUT = os.path.join(HERE, "items", "wave4.jsonl")
TODAY = "2026-11-09"
VERSION = "1.4-candidate"

br.OUT = OUT
br.TODAY = TODAY
br.VERSION = VERSION

# --- quotas
MOVE_QUOTA = {"P.": 2, "S.W.": 2, "N.W.": 2, "A.": 2, "A.2d": 1, "N.E.": 1, "S.E.": 1, "S.E.2d": 1, "P.2d": 1,
              "So.": 1, "N.E.2d": 1, "S.W.2d": 1, "N.W.2d": 1, "A.D.2d": 1, "N.J.": 1, "N.Y.S.2d": 1}
# The modern strata (So. 3d, A.3d, A.D.3d, P.3d) are table decisions with no citing opinions, and the S.W.2d rows
# have a second cluster at the printed page, so none passed evidence; the older strata take two (N.W.2d three) each,
# which is every row they had that passed.
STRAY_QUOTA = {"So. 3d": 2, "N.W.2d": 3, "A.D.3d": 1, "A.3d": 2, "So.": 2, "P.": 2, "P.3d": 1, "P.2d": 2,
               "S.W.2d": 1, "S.E.2d": 2}
NY_QUOTA = {"8": 7, "9": 9}  # by volume hundred (N.Y.S.2d 800s, 900s: the rows with 3+ named citing sentences are 2007-2014)
POOL_MULT = 4          # pool rows per stratum slot
NY_MIN_NAME_HITS = 3   # XREP204's own count of citing sentences that print the N.Y.S.2d key with a party word
N_NY_CONTROLS = 3
N_RG_CONTROLS = 3

PROVENANCE = br.PROVENANCE


def jload(p):
    with open(p) as f:
        return json.load(f)


jsonl = br.jsonl
wjsonl = br.wjsonl
parse_cite = br.parse_cite


def used_clusters():
    ids = br.used_clusters()
    for name in ("regional.jsonl", "wave3.jsonl"):
        for row in jsonl(os.path.join(HERE, "items", name)):
            e = row.get("evidence") or {}
            if e.get("cluster_id"):
                ids.add(int(e["cluster_id"]))
    return ids


def prior_ledgers():
    s = set()
    for p in (br.FIX_A, br.FIX_C, br.FIX_91, os.path.join(LANES, "RESCORE166/fix/fixA2b.json"),
              os.path.join(LANES, "RESCORE166/fix/fixC2.json")):
        s |= {int(r["cid"]) for r in jload(p)}
    return s


def pool_row(db, cid, klass, kind, ours, alt, other_cids, source, n_alt=0, extra=None):
    cm = br.case_meta(db, cid)
    name = cm.get("case_name")
    others = {str(o): [f"{v} {r} {p}" for v, r, p in db.execute(
        "SELECT volume, reporter, page FROM citations WHERE cluster_id=?", (int(o),))] for o in other_cids}
    row = {"cid": int(cid), "klass": klass, "kind": kind, "reporter": parse_cite(alt)[1], "ours": ours, "alt": alt,
           "n_alt": n_alt, "n_ours": None, "tier": None, "other_cites": others, "source": source,
           "case_name": name, "date_filed": cm.get("date_filed"), "court_id": cm.get("court_id"),
           "docket_number": cm.get("docket_number"), "token": br.name_token(name or ""),
           "alt_years": br.volume_years(db, *parse_cite(alt)[:2]),
           "ours_years": br.volume_years(db, *parse_cite(ours)[:2]),
           "alt_holders_meta": br.holders(db, alt), "ours_holders_meta": br.holders(db, ours),
           "cl_cites": [f"{v} {r} {p}" for v, r, p in db.execute(
               "SELECT volume, reporter, page FROM citations WHERE cluster_id=? ORDER BY id", (int(cid),))],
           "other_names": {str(o): (br.case_meta(db, o).get("case_name"), br.case_meta(db, o).get("date_filed"))
                           for o in other_cids}}
    row.update(extra or {})
    return row


def spread(cands, k, key):
    """Up to k rows, one per `key` value first, then the rest in order."""
    out, seen = [], set()
    for passn in (0, 1):
        for r in cands:
            if len(out) >= k or r in out:
                continue
            kv = key(r)
            if passn == 0 and kv in seen:
                continue
            seen.add(kv)
            out.append(r)
    return out


# ---------------------------------------------------------------- pools

def draw_move(db, used):
    d = jload(DECISIONS)
    rows = [x for x in d if x["act"] == "move-page" and x["cid"] not in used]
    pool = []
    for rep, q in MOVE_QUOTA.items():
        cand = [x for x in rows if x["kr"] == rep and br.name_token(x["case_name"] or "")]
        cand.sort(key=lambda x: (-x["alt_n"], x["cid"]))
        for x in spread(cand, q * POOL_MULT, lambda x: (x["date_filed"] or "????")[:3]):
            ours = f"{x['kv']} {rep} {x['kp']}"
            alt = f"{x['kv']} {rep} {x['alt_page']}"
            others = [h for h in br.holders(db, ours) if h != x["cid"]]
            if not others:
                continue
            pool.append(pool_row(db, x["cid"], "C", "move", ours, alt, others[:1], "PAGE195 move-page",
                                 n_alt=x["alt_n"], extra={"stratum": f"move/{rep}", "page195": x}))
    return pool


def draw_stray(db, used):
    rows = []
    for x in jload(PRIM)["ex"]:
        rows.append({"cid": x["cid"], "ours": x["now"], "alt": x["new"], "owner": x["now_owner"],
                     "source": "PRIM203 stray first page"})
    for x in jload(DECISIONS):
        if x["act"] == "drop" and "this row is a stray" in x["why"]:
            rows.append({"cid": x["cid"], "ours": f"{x['kv']} {x['kr']} {x['kp']}",
                         "alt": f"{x['kv']} {x['kr']} {x['alt_page']}",
                         "owner": x["k_new_owner"] if x.get("k_owner") == x["cid"] else x.get("k_owner"),
                         "source": "PAGE195 drop-stray"})
    pool, seen = [], set()
    for rep, q in STRAY_QUOTA.items():
        cand = []
        for x in rows:
            po, pa = parse_cite(x["ours"]), parse_cite(x["alt"])
            if not po or not pa or po[1] != rep or pa[1] != rep or x["cid"] in used or x["cid"] in seen:
                continue
            if pa[2].startswith("0") or len(pa[2]) > len(po[2]) + 1:  # '1 So. 2d 024', '248 S.W.3d 4822': OCR junk
                continue
            cand.append(x)
        cand.sort(key=lambda x: x["cid"])
        k = 0
        for x in spread(cand, len(cand), lambda x: parse_cite(x["ours"])[0]):
            if k >= q * POOL_MULT:
                break
            cl = {f"{v} {r} {p}" for v, r, p in db.execute(
                "SELECT volume, reporter, page FROM citations WHERE cluster_id=?", (x["cid"],))}
            if x["ours"] not in cl or x["alt"] not in cl:  # both pages must be on the case in CourtListener
                continue
            others = [h for h in br.holders(db, x["ours"]) if h != x["cid"]]
            if not others:
                continue
            owner = x["owner"] if x["owner"] in others else others[0]
            r = pool_row(db, x["cid"], "C", "stray", x["ours"], x["alt"], [owner], x["source"],
                         extra={"stratum": f"stray/{rep}"})
            if not r["case_name"] or not r["token"]:
                continue
            pool.append(r)
            seen.add(x["cid"])
            k += 1
    return pool


def draw_ny(db, used):
    rows = jload(NY_CLASS)
    ev = jload(NY_EV)
    keys = Counter((r["vol"], r["page"]) for r in rows)
    pool = []
    for band, q in NY_QUOTA.items():
        cand = [r for r in rows if r["k"] == "RELABEL_free" and r["id"] is not None and r["court"] == "nyappdiv"
                and str(r["vol"] // 100) == band and keys[(r["vol"], r["page"])] == 1 and r["cid"] not in used
                and (ev.get(str(r["id"])) or {}).get("name_hits", 0) >= NY_MIN_NAME_HITS and br.name_token(r["name"])]
        cand.sort(key=lambda r: (-ev[str(r["id"])]["name_hits"], r["cid"]))
        for r in spread(cand, q * POOL_MULT, lambda r: r["vol"] // 10):
            ours = f"{r['vol']} N.Y.2d {r['page']}"
            alt = f"{r['vol']} N.Y.S.2d {r['page']}"
            e = ev[str(r["id"])]
            pool.append(pool_row(db, r["cid"], "A", "ny", ours, alt, [], "XREP204 RELABEL_free",
                                 n_alt=e["n"], extra={"stratum": f"ny/{band}00s", "ny_name_hits": e["name_hits"],
                                                      "cl_citation_id": r["id"]}))
    return pool


def draw_controls(db, touched):
    """NY: Appellate Division cases CourtListener already files under N.Y.S.2d in the same volume bands.
    Regional: ordinary cases in the volumes of the kept move rows. 15-80 citing opinions, one holder, no fix ledger."""
    out = []
    for vol in (650, 760, 870, 940):
        rows = db.execute(
            "SELECT t.cluster_id, t.page, c.case_name, c.date_filed, c.court_id, c.citation_count FROM citations t "
            "JOIN cases c ON c.cluster_id=t.cluster_id WHERE t.volume=? AND t.reporter='N.Y.S.2d' "
            "AND c.court_id='nyappdiv' AND c.citation_count BETWEEN 15 AND 80 ORDER BY t.page+0", (str(vol),)).fetchall()
        n = 0
        for cid, pg, name, filed, ct, cnt in rows:
            cite = f"{vol} N.Y.S.2d {pg}"
            if cid in touched or not name or not br.name_token(name) or len(br.holders(db, cite)) != 1:
                continue
            out.append({"cid": cid, "cite": cite, "reporter": "N.Y.S.2d", "case_name": name, "date_filed": filed,
                        "court_id": ct, "citation_count": cnt, "token": br.name_token(name), "group": "ny"})
            n += 1
            if n == 3:
                break
    for rep, vol in (("P.", "62"), ("S.W.", "189"), ("N.W.", "29"), ("A.", "115"), ("So.", "54")):
        rows = db.execute(
            "SELECT t.cluster_id, t.page, c.case_name, c.date_filed, c.court_id, c.citation_count FROM citations t "
            "JOIN cases c ON c.cluster_id=t.cluster_id WHERE t.volume=? AND t.reporter=? "
            "AND c.citation_count BETWEEN 15 AND 80 ORDER BY t.page+0", (vol, rep)).fetchall()
        n = 0
        for cid, pg, name, filed, ct, cnt in rows:
            cite = f"{vol} {rep} {pg}"
            if cid in touched or not name or not br.name_token(name) or len(br.holders(db, cite)) != 1:
                continue
            out.append({"cid": cid, "cite": cite, "reporter": rep, "case_name": name, "date_filed": filed,
                        "court_id": ct, "citation_count": cnt, "token": br.name_token(name), "group": "rg"})
            n += 1
            if n == 2:
                break
    return out


def draw_pools():
    db = br.meta_db()
    used = used_clusters()
    os.makedirs(OUT, exist_ok=True)
    mp = draw_move(db, used)
    sp = draw_stray(db, used | {p["cid"] for p in mp})
    nyp = draw_ny(db, used)
    touched = used | prior_ledgers() | {x["cid"] for x in jload(DECISIONS)} | {x["cid"] for x in jload(PRIM)["ex"]}
    touched |= {r["cid"] for r in jload(NY_CLASS)}
    touched |= {int(r["cid"]) for r in jsonl(os.path.join(LANES, "RESCORE166/x/neigh.jsonl"))}
    cp = draw_controls(db, touched)
    wjsonl(os.path.join(OUT, "pool_move.jsonl"), mp)
    wjsonl(os.path.join(OUT, "pool_stray.jsonl"), sp)
    wjsonl(os.path.join(OUT, "pool_ny.jsonl"), nyp)
    wjsonl(os.path.join(OUT, "pool_controls.jsonl"), cp)
    print("move pool", len(mp), dict(Counter(p["stratum"] for p in mp)))
    print("stray pool", len(sp), dict(Counter(p["stratum"] for p in sp)))
    print("ny pool", len(nyp), dict(Counter(p["stratum"] for p in nyp)))
    print("control pool", len(cp), dict(Counter(p["group"] for p in cp)))


# ---------------------------------------------------------------- evidence (network)

def quota_of(stratum):
    kind, key = stratum.split("/", 1)
    if kind == "move":
        return MOVE_QUOTA[key]
    if kind == "stray":
        return STRAY_QUOTA[key]
    return NY_QUOTA[key[0]]


def run_evidence():
    for name in ("move", "stray", "ny"):
        pool = jsonl(os.path.join(OUT, f"pool_{name}.jsonl"))
        out, kept = [], Counter()
        for i, p in enumerate(pool):
            if kept[p["stratum"]] >= quota_of(p["stratum"]) + 1:  # quota + one spare that pass evaluate()
                continue
            ev = br.gather(p)
            ok, why, _ = evaluate(p, ev)
            if ok:
                kept[p["stratum"]] += 1
            out.append(ev)
            print(f"{name} {i+1}/{len(pool)} {p['cid']} {p['alt']} citers={len(ev['alt_citers'])} "
                  f"ours_named={len(ev['ours_citers'])} cc={ev['check_citation']['verdict']} -> {why[:70]}", flush=True)
        wjsonl(os.path.join(OUT, f"evidence_{name}.jsonl"), out)
    out = []
    for p in jsonl(os.path.join(OUT, "pool_controls.jsonl")):
        cc = br.sy_call("check_citation", {"citation": p["cite"], "expected_case_name": p["case_name"]})
        js = (cc or {}).get("json") or {}
        m = (js.get("matches") or [{}])[0]
        hits = {}
        for form in (p["cite"], br.undotted(p["cite"])):
            res = br.sy_call("search_cases", {"q": f'{p["token"]} w/15 "{form}"', "compact": True, "per_page": 20})
            for h in br.snippet_hits(res, p["cite"], p["token"], p["cid"]):
                hits.setdefault(h["cluster_id"], h)
            if len(hits) >= 2:
                break
        p.update({"check_citation": {"verdict": js.get("verdict"), "cluster_id": m.get("cluster_id"),
                                     "bluebook": m.get("bluebook"), "flag": (m.get("treatment") or {}).get("flag"),
                                     "name_check": (js.get("name_check") or {}).get("verdict")},
                  "citers": list(hits.values())})
        out.append(p)
        print("control", p["cite"], p["case_name"][:40], js.get("verdict"), m.get("cluster_id") == p["cid"],
              (m.get("treatment") or {}).get("flag"), len(hits), flush=True)
    wjsonl(os.path.join(OUT, "evidence_controls.jsonl"), out)


def evaluate(p, ev):
    """build_regional.evaluate, plus: the old cite is on the case in CourtListener; for a stray, the other case at the
    old cite has another name; the bluebook Syfert returns leads with the printed cite."""
    keep, why, facts = br.evaluate(p, ev)
    if not keep:
        return keep, why, facts
    if p["ours"] not in p["cl_cites"]:
        return False, f"{p['ours']} is not on the case in the CourtListener-derived meta", facts
    if p["kind"] in ("move", "stray"):
        oc, (oname, _) = next(iter(p["other_names"].items()))
        if not oname or br.name_token(oname) == p["token"]:
            return False, f"the other case at {p['ours']} ({oname}) shares the party word; may be a twin", facts
    if p["kind"] == "move" and p["alt"] in p["cl_cites"]:
        return False, "the printed cite is already on the case (a stray, not a move)", facts
    bb = ev["check_citation"].get("bluebook") or ""
    if p["alt"] not in bb:
        return False, f"Syfert bluebook does not carry {p['alt']} ({bb})", facts
    if ev["check_citation"].get("name_check") not in ("match", None):
        return False, f"name check {ev['check_citation'].get('name_check')}", facts
    return True, "ok", facts


# ---------------------------------------------------------------- items

ID_PREFIX = {"move": "pg-m", "stray": "pg-s", "ny": "ny"}


def make_item(p, ev, facts, shape, iid):
    it = br.build_item(p, ev, facts, shape, iid)
    it["evidence"]["fix_source"] = p["source"]
    it["evidence"]["cl_cites_in_order"] = p["cl_cites"]
    if p["kind"] == "ny":
        it["class"] = "nyseries"
        it["fix_class"] = "N.Y.2d-label"
        it["court_id"] = "nyappdiv"
        it["evidence"]["fix_class"] = "XREP204 RELABEL_free"
        it["evidence"]["xrep204_citing_events"] = p["n_alt"]
        it["evidence"]["xrep204_name_hits"] = p["ny_name_hits"]
        it["evidence"]["series_check"] = (f"N.Y.2d (Court of Appeals) ran to volume 100; {p['ours']} is an impossible "
                                          f"N.Y.2d cite. The Appellate Division decision is in N.Y.S.2d at the same "
                                          f"volume and page; no other cluster holds {p['alt']}.")
        if shape == "i":
            it["gold"]["note"] = (f"real cite that the CourtListener index lacks: it files this Appellate Division case "
                                  f"as {p['ours']} (N.Y.2d ended at volume 100), so {p['alt']} looks fabricated; the "
                                  f"answer must add a fact not in the passage (date or court)")
        else:
            it["gold"]["note"] = (f"{p['ours']} is the label CourtListener stores; N.Y.2d ended at volume 100. The case "
                                  f"is an Appellate Division decision reported at {p['alt']}; citing courts print that")
            it["gold"]["series"] = "N.Y.S.2d"
            # The official Appellate Division cite is an equally correct way to cite the case (New York practice
            # leads with it, and CourtListener's own reply prints it as a parallel), so it also passes; only the
            # impossible N.Y.2d label fails.
            ad = [c for c in p["cl_cites"] if re.fullmatch(r"\d+ A\.D\.[23]d \d+", c)]
            it["gold"]["any_right"] = [p["alt"]] + ad
            it["gold"]["right"] = []
            it["gold"]["note"] += (f"; the official cite {ad[0]} also passes" if ad else "")
    else:
        it["class"] = "samepage"
        it["fix_class"] = "move" if p["kind"] == "move" else "stray"
        it["evidence"]["fix_class"] = p["kind"]
        if p["kind"] == "stray":
            it["gold"]["note"] += (f". CourtListener lists both {p['ours']} and {p['alt']} on this case, "
                                   f"{p['ours']} first; {p['ours']} is the other case's first page")
            it["evidence"]["stray_listed_first"] = p["cl_cites"].index(p["ours"]) < p["cl_cites"].index(p["alt"])
    return it


def build_items(drops):
    items = []
    for name in ("move", "stray", "ny"):
        pool = jsonl(os.path.join(OUT, f"pool_{name}.jsonl"))
        evs = {e["cid"]: e for e in jsonl(os.path.join(OUT, f"evidence_{name}.jsonl"))}
        taken = Counter()
        order = list(dict.fromkeys(p["stratum"] for p in pool))  # stratum index, for alternating shapes
        for p in pool:
            ev = evs.get(p["cid"])
            if ev is None:
                continue
            keep, why, facts = evaluate(p, ev)
            if not keep:
                drops.append({"cid": p["cid"], "alt": p["alt"], "ours": p["ours"], "stage": "evidence",
                              "class": name, "why": why})
                continue
            st = p["stratum"]
            q = quota_of(st)
            if taken[st] >= q + 1:
                continue
            # stray: shape (ii) only. A passage with the case's own page is confirmed by CourtListener (it holds that
            # page too), so shape (i) is no trap.
            # shapes alternate within a stratum and start on alternate shapes across strata (build_wave3's rule), so
            # the kept rows, the first of each stratum, are balanced too
            si = order.index(st)
            shape = "ii" if name == "stray" else ("i" if (si + taken[st]) % 2 == 0 else "ii")
            iid = f"{ID_PREFIX[name]}-{br.SHORT.get(p['reporter'], re.sub(r'[^a-z0-9]', '', p['reporter'].lower()))}" \
                  f"-{taken[st] + 1}" if name != "ny" else f"ny-{st.split('/')[1][:1]}-{taken[st] + 1}"
            it = make_item(p, ev, facts, shape, iid)
            if shape == "ii" and grade.norm(p["alt"]) in grade.norm(it["text"]):
                drops.append({"cid": p["cid"], "stage": "echo", "why": "passage contains the gold cite"})
                continue
            if shape == "i" and not it["gold"]["any_right"]:
                drops.append({"cid": p["cid"], "stage": "echo", "why": "no date/court fact outside the passage"})
                continue
            it["_stratum"] = st
            it["_quota"] = q
            items.append(it)
            taken[st] += 1
    return items


def control_items(drops):
    out, n = [], Counter()
    for c in jsonl(os.path.join(OUT, "evidence_controls.jsonl")):
        cc = c["check_citation"]
        why = None
        if cc.get("cluster_id") != c["cid"] or cc.get("verdict") != "found":
            why = f"MCP does not resolve it ({cc.get('cluster_id')}, {cc.get('verdict')})"
        elif cc.get("flag") not in ("green", None) or cc.get("name_check") != "match":
            why = f"flag {cc.get('flag')} / name {cc.get('name_check')}"
        elif len(c["citers"]) < 2:
            why = f"{len(c['citers'])} citing opinions print it with the name"
        elif c["cite"] not in (cc.get("bluebook") or ""):
            why = f"bluebook {cc.get('bluebook')}"
        if why:
            drops.append({"cid": c["cid"], "cite": c["cite"], "stage": "evidence", "class": "control", "why": why})
            continue
        cap = N_NY_CONTROLS if c["group"] == "ny" else N_RG_CONTROLS
        if n[c["group"]] >= cap + 1:
            continue
        n[c["group"]] += 1
        it = br.control_item(c, f"{'ny' if c['group'] == 'ny' else 'pg'}-co-{n[c['group']]}")
        it["evidence"]["source"] = f"syfert.com MCP check_citation + search_cases, {TODAY}"
        it["version"] = VERSION
        it["_stratum"] = f"control/{c['group']}"
        it["_quota"] = cap
        out.append(it)
    return out


# ---------------------------------------------------------------- CourtListener (network)

CL_CID = re.compile(r"(?:cluster_id=|Cluster ID:\s+)(\d+)")


def cl_body(row):
    base = os.path.join(OUT, "cl", row["id"])
    if not (os.path.exists(base + ".txt") and os.path.exists(base + ".in")):
        return None
    if open(base + ".in").read().strip() != row["text"].strip():
        return None
    return open(base + ".txt").read()


def run_cl(rows, cap):
    import time
    import clmcp
    d = os.path.join(OUT, "cl")
    os.makedirs(d, exist_ok=True)
    try:
        h = clmcp.health()
    except Exception as e:
        raise SystemExit("CourtListener health failed: " + str(e)[:200])
    with open(os.path.join(d, "health.json"), "w") as f:
        json.dump(h, f, indent=2)
    calls = 0
    for row in rows:
        if cl_body(row) is not None:
            continue
        if calls >= cap:
            print("cap reached", cap)
            break
        if calls:
            time.sleep(2.0)
        calls += 1
        try:
            body = clmcp.analyze(row["text"])
        except Exception as e:
            body = "ERROR " + str(e)[:500]
        with open(os.path.join(d, row["id"] + ".txt"), "w") as f:
            f.write(body if body.endswith("\n") else body + "\n")
        with open(os.path.join(d, row["id"] + ".in"), "w") as f:
            f.write(row["text"] + "\n")
        print("cl", row["id"], (body.strip().splitlines() or [""])[-1][:100], flush=True)
        if body.startswith("ERROR") and ("401" in body or "403" in body):
            raise SystemExit("CourtListener auth failure; stopping: " + body[:200])
    print("cl calls", calls)


def cl_verdict(row, body):
    """(drop, detail). Drop when the raw CL arm answers the item, or when CourtListener does not show the error the
    item is built on (shape ii: CL must return the case at the old cite; shape i: CL must not resolve the printed cite
    to the case)."""
    import score
    if body is None:
        return None, "no CL reply on disk"
    if body.startswith("ERROR"):
        return None, body[:160]
    g = grade.grade_item(body, row["gold"], row["text"])
    cases = score.parse(body)["cases"]
    st = cases[0]["status"] if cases else ("NONE" if "No citations found" in body else "?")
    cids = [int(x) for x in CL_CID.findall(body)]
    detail = f"status={st} clusters={cids[:4]} grade={g['passed']}"
    if g["passed"]:
        return (row.get("kind") != "control"), detail + " (grader passes the raw CL body)"
    if row.get("kind") == "control":
        return False, detail
    cid = row["evidence"]["cluster_id"]
    alt = row["evidence"]["printed_cite"]
    if row["shape"] == "ii" and (alt in body or br.undotted(alt) in body):
        return True, detail + " (CL names the printed cite)"
    if row["shape"] == "i":  # the reply echoes the passage's cite, so only the status and cluster count here
        if st == "FOUND" and cid in cids:
            return True, detail + " (CL resolves the printed cite to the case)"
        return False, detail
    if cid not in cids:
        return True, detail + " (CL does not return the case at the old cite: the error is not CourtListener's)"
    return False, detail


# ---------------------------------------------------------------- main

EXCLUDE = {}


def build(run_cl_step, cap):
    drops = []
    items = build_items(drops)
    controls = control_items(drops)
    wjsonl(os.path.join(OUT, "pre_cl.jsonl"), [{k: v for k, v in r.items() if not k.startswith("_")}
                                               for r in items + controls])
    if run_cl_step:
        run_cl(items + controls, cap)
    final, cl_rows, spares, filled = [], [], [], Counter()
    for row in items + controls:
        body = cl_body(row)
        drop, detail = cl_verdict(row, body)
        cl_rows.append({"id": row["id"], "text": row["text"], "cl": detail, "drop": drop})
        if drop is None:
            drops.append({"id": row["id"], "stage": "cl", "why": "not run: " + detail})
            continue
        if drop:
            drops.append({"id": row["id"], "cid": row["evidence"]["cluster_id"], "text": row["text"], "stage": "cl",
                          "why": "raw CourtListener arm: " + detail})
            continue
        if row["evidence"]["cluster_id"] in EXCLUDE:
            drops.append({"id": row["id"], "cid": row["evidence"]["cluster_id"], "text": row["text"],
                          "stage": "review", "why": EXCLUDE[row["evidence"]["cluster_id"]]})
            continue
        st, q = row.pop("_stratum", None), row.pop("_quota", None)
        if st is not None:
            if filled[st] >= q:
                spares.append({"id": row["id"], "text": row["text"], "why": "spare; stratum full"})
                continue
            filled[st] += 1
        row["evidence"]["courtlistener_raw"] = detail
        final.append(row)
    bad = [(r["id"], why) for r in final for ok, why in [grade.self_check(r)] if not ok]
    wjsonl(ITEMS_OUT, final)
    wjsonl(os.path.join(OUT, "drops.jsonl"), drops)
    wjsonl(os.path.join(OUT, "spares.jsonl"), spares)
    wjsonl(os.path.join(OUT, "cl_verdicts.jsonl"), cl_rows)
    summ = {"items": len(final),
            "by_class_shape": dict(Counter(f"{r['class']}/{r.get('shape', '-')}/{r.get('fix_class', '-')}"
                                           for r in final)),
            "by_reporter": dict(Counter(r["reporter"] for r in final)),
            "drops_by_stage": dict(Counter(f"{d['stage']}/{d.get('class', '')}" for d in drops)),
            "self_check_failures": bad}
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump(summ, f, indent=1)
    print(json.dumps(summ, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", action="store_true")
    ap.add_argument("--pool", action="store_true")
    ap.add_argument("--evidence", action="store_true")
    ap.add_argument("--cl", action="store_true")
    ap.add_argument("--max", type=int, default=150)
    a = ap.parse_args()
    br.NETWORK = a.network
    if (a.evidence or a.cl) and not a.network:
        raise SystemExit("--evidence / --cl call the network; add --network")
    if a.pool:
        draw_pools()
        return
    if a.evidence:
        run_evidence()
        return
    build(a.cl, a.max)


if __name__ == "__main__":
    main()
