# Build the v1.2 CANDIDATE regional-reporter wave from the 2026-11-07 regional number corrections.
#
# usage:
#   python3 build_regional.py --pool                      # draw the stratified pool (offline)
#   python3 build_regional.py --evidence --network        # Syfert MCP check_citation + search_cases per pool row
#   python3 build_regional.py --controls --network        # draw + check the control rows
#   python3 build_regional.py --cl --network [--max 120]  # raw CourtListener analyze_citations per candidate item
#   python3 build_regional.py                             # offline: build items from what is on disk
#
# No network call is made unless --network is given. Every network reply is saved under OUT and the
# offline build reads only those files, the fix ledgers and caselaw_meta.db (opened read-only).
# Writes items/regional.jsonl and OUT/{drops.jsonl,pre_cl.jsonl,summary.json}.
# It never touches items/tasks.jsonl or VERSION.
#
# Sources (read-only):
#   class A  RESCORE166/fix/fix1332.json  (cid, ours = old CourtListener number, alt = the number citers print)
#   class C  RESCORE166/fix/classC.json   (ours is also the first page of another case: other_cites)
#   FIX154   FIX154/src/fix91.json        (earlier batch, same kind as class A)
#   names    RESCORE166/x/names.json      (cid -> [case name, date, court])
import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time

import grade

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "20261107-regional-wave")
LANES = os.path.expanduser("~/projects/caselaw-tools/tony4_20261102/lanes")
FIX_A = os.path.join(LANES, "RESCORE166/fix/fix1332.json")
FIX_C = os.path.join(LANES, "RESCORE166/fix/classC.json")
FIX_91 = os.path.join(LANES, "FIX154/src/fix91.json")
NAMES = os.path.join(LANES, "RESCORE166/x/names.json")
META = "/home/graham/projects/courtlistener/pkg/caselaw_meta.db"
ITEMS_OUT = os.path.join(HERE, "items", "regional.jsonl")
TODAY = "2026-11-07"
VERSION = "1.2-candidate"

REPORTERS = ["S.E.", "S.E.2d", "N.W.", "N.W.2d", "N.E.", "N.E.2d", "P.", "P.2d",
             "A.", "A.2d", "So.", "So. 2d", "S.W.", "S.W.2d"]
PER_REP_A = 3
PER_REP_C = 2

ABSENT_I = ["not found", "does not exist", "may be incorrect", "no such case", "cannot find",
            "could not find", "fabricated", "hallucinat", "not a real case"]
ABSENT_CONTROL = ["not found", "does not exist", "may be incorrect", "no such case", "cannot find",
                  "could not find", "fabricated", "misprint", "typo", "interior page", "not the first page",
                  "wrong series", "wrong reporter", "wrong page", "wrong volume", "should be", "does not match",
                  "name mismatch", "overruled", "abrogated", "receded", "no longer good law", "unpublished"]
PROVENANCE = ("The corpus behind syfert.com is itself CourtListener-derived, so the gold does not rest on our "
              "index: it rests on the citing courts' own printed text, quoted below with each citing opinion's "
              "cluster id, name and date.")

GENERIC = set("""state states people commonwealth city county town village township borough in re ex parte the of
united v. vs. inc inc. co co. company corp corp. corporation matter estate et al and & r. r railroad railway ry ry.
insurance ins ins. bank national first board school district mutual life fire casualty trust savings loan american
mfg mfg. association ass'n assn bros bros. sons heirs guardianship adoption marriage application petition
north south east west new county, city, state, appeal appeals department dept dept. commission
""".split())

CITE_RX = re.compile(r"^(\d+) (.+) (\d+)$")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
MON_AB = ["Jan.", "Feb.", "Mar.", "Apr.", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]


def jload(p):
    with open(p) as f:
        return json.load(f)


def jsonl(p):
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return [json.loads(x) for x in f if x.strip()]


def wjsonl(p, rows):
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def parse_cite(s):
    m = CITE_RX.match(s)
    return (m.group(1), m.group(2), m.group(3)) if m else None


def undotted(cite):
    """'218 S.E.2d 318' -> '218 SE2d 318' (the Georgia and Michigan spelling)."""
    v, r, p = parse_cite(cite)
    return f"{v} {r.replace('.', '').replace(' ', '')} {p}"


def meta_db():
    c = sqlite3.connect(f"file:{META}?mode=ro", uri=True)
    c.execute("PRAGMA query_only=ON")
    return c


def name_token(name):
    """One distinctive party word to anchor a proximity search (w/15) and to find the name in a snippet."""
    parts = re.split(r"\s+v\.?\s+|\s+vs\.?\s+", name, maxsplit=1)
    for party in parts:
        words = re.findall(r"[A-Za-z][A-Za-z'\-]+", party)
        cand = [w for w in words if w.lower() not in GENERIC and len(w) >= 4]
        if cand:
            return cand[0]
    return None


def volume_years(db, vol, rep):
    """(p10, p50, p90, n) of decision years for clusters at this reporter volume in the local CL-derived meta."""
    rows = db.execute(
        "SELECT substr(c.date_filed,1,4) FROM citations t JOIN cases c ON c.cluster_id=t.cluster_id "
        "WHERE t.volume=? AND t.reporter=? AND c.date_filed IS NOT NULL", (vol, rep)).fetchall()
    ys = sorted(int(y[0]) for y in rows if y[0] and y[0].isdigit())
    if not ys:
        return None
    q = lambda f: ys[min(len(ys) - 1, int(f * len(ys)))]
    return (q(0.1), q(0.5), q(0.9), len(ys))


def holders(db, cite):
    v, r, p = parse_cite(cite)
    return [x[0] for x in db.execute(
        "SELECT DISTINCT cluster_id FROM citations WHERE volume=? AND reporter=? AND page=?", (v, r, p))]


def case_meta(db, cid):
    r = db.execute("SELECT case_name, date_filed, court_id, docket_number FROM cases WHERE cluster_id=?",
                   (int(cid),)).fetchone()
    return dict(zip(("case_name", "date_filed", "court_id", "docket_number"), r)) if r else {}


def used_clusters():
    ids = set()
    for row in jsonl(os.path.join(HERE, "items", "tasks.jsonl")):
        e = row.get("evidence") or {}
        if isinstance(e, dict) and e.get("cluster_id"):
            ids.add(int(e["cluster_id"]))
        g = row.get("gold") or {}
        if isinstance(g, dict) and g.get("cluster_id"):
            ids.add(int(g["cluster_id"]))
    return ids


# ---------------------------------------------------------------- pool

def draw_pool():
    names = jload(NAMES)
    used = used_clusters()
    rows = []
    for r in jload(FIX_A):
        rows.append(dict(r, klass="A", source="RESCORE166 fix1332"))
    for r in jload(FIX_C):
        rows.append(dict(r, klass="C", source="RESCORE166 classC"))
    for r in jload(FIX_91):
        rows.append(dict(r, klass="A", source="FIX154 fix91", n_alt=r.get("citers", 0)))
    db = meta_db()
    pool = []
    for rep in REPORTERS:
        for klass, k in (("A", PER_REP_A), ("C", PER_REP_C)):
            cand = [r for r in rows if r["klass"] == klass and parse_cite(r["alt"])[1] == rep
                    and parse_cite(r["ours"])[1] == rep and int(r["cid"]) not in used
                    and int(parse_cite(r["ours"])[2]) > 0]  # '140 P. 000' is a placeholder, not a passage
            # strongest evidence first; then one per decade so a reporter spans its eras
            cand.sort(key=lambda r: (-int(r.get("n_alt") or 0), int(r["cid"])))
            picked, decades = [], set()
            for passn in (0, 1):
                for r in cand:
                    if len(picked) >= k + 2:  # two spares per stratum for evidence drops
                        break
                    if r in picked:
                        continue
                    nm = names.get(str(r["cid"])) or [r.get("name"), None, None]
                    if not nm[0] or not name_token(nm[0]):
                        continue
                    dec = (nm[1] or "????")[:3]
                    if passn == 0 and dec in decades:
                        continue
                    decades.add(dec)
                    picked.append(r)
            for r in picked:
                nm = names.get(str(r["cid"])) or [r.get("name"), None, None]
                cm = case_meta(db, r["cid"])
                pool.append({
                    "cid": int(r["cid"]), "klass": klass, "reporter": rep, "ours": r["ours"], "alt": r["alt"],
                    "n_alt": int(r.get("n_alt") or 0), "n_ours": r.get("n_ours"), "tier": r.get("tier"),
                    "other_cites": r.get("other_cites") or {}, "source": r["source"],
                    "case_name": nm[0], "date_filed": nm[1] or cm.get("date_filed"),
                    "court_id": nm[2] or cm.get("court_id"), "docket_number": cm.get("docket_number"),
                    "token": name_token(nm[0]),
                    "alt_years": volume_years(db, *parse_cite(r["alt"])[:2]),
                    "ours_years": volume_years(db, *parse_cite(r["ours"])[:2]),
                    "alt_holders_meta": holders(db, r["alt"]),
                    "other_names": {oc: (case_meta(db, oc).get("case_name"), case_meta(db, oc).get("date_filed"))
                                    for oc in (r.get("other_cites") or {})},
                })
    os.makedirs(OUT, exist_ok=True)
    wjsonl(os.path.join(OUT, "pool.jsonl"), pool)
    from collections import Counter
    print("pool", len(pool), Counter((p["reporter"], p["klass"]) for p in pool))


# ---------------------------------------------------------------- evidence (network)

def sy_path(key):
    return os.path.join(OUT, "syfert", key + ".json")


def sy_call(tool, args):
    """Cached Syfert MCP call; the key is a hash of the tool + args."""
    key = tool + "-" + hashlib.sha1(json.dumps([tool, args], sort_keys=True).encode()).hexdigest()[:16]
    p = sy_path(key)
    if os.path.exists(p):
        return jload(p)
    if not NETWORK:
        return None
    import syfmcp
    try:
        res = syfmcp.call(tool, args)
    except Exception as e:
        res = {"tool": tool, "args": args, "is_error": True, "text": "ERROR " + str(e)[:300], "json": None}
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    return res


def snippet_hits(res, cite, token, self_cid):
    """Citing opinions whose snippet prints `cite` with `token` in the 160 chars before it."""
    out = []
    js = (res or {}).get("json") or {}
    forms = [cite, undotted(cite)]
    for row in js.get("results") or []:
        cid = row.get("cluster_id")
        if cid == self_cid:
            continue
        snip = " ".join((row.get("snippet") or "").split())
        snip_n = re.sub(r"\s+,", ",", snip)
        for form in forms:
            # word-bounded: '18 S.W. 312' must not match inside '218 S.W. 312'
            m = re.search(r"(?<![\d])" + re.escape(form) + r"(?![\d])", snip_n)
            if not m:
                continue
            before = snip_n[max(0, m.start() - 160):m.start()]
            if token.lower() in before.lower():
                out.append({"cluster_id": cid, "bluebook": row.get("bluebook"), "date_filed": row.get("date_filed"),
                            "printed_as": form, "snippet": snip})
                break
    return out


def gather(p):
    """Syfert evidence for one pool row: check_citation(alt) + citers printing alt (+ citers printing ours)."""
    ev = {"cid": p["cid"]}
    cc = sy_call("check_citation", {"citation": p["alt"], "expected_case_name": p["case_name"]})
    js = (cc or {}).get("json") or {}
    m = (js.get("matches") or [{}])[0]
    ev["check_citation"] = {"verdict": js.get("verdict"), "cluster_id": m.get("cluster_id"),
                            "case_name": m.get("case_name"), "bluebook": m.get("bluebook"), "court": m.get("court"),
                            "date_filed": m.get("date_filed"), "flag": (m.get("treatment") or {}).get("flag"),
                            "name_check": (js.get("name_check") or {}).get("verdict")}
    hits = {}
    for form in (p["alt"], undotted(p["alt"])):
        res = sy_call("search_cases", {"q": f'{p["token"]} w/15 "{form}"', "compact": True, "per_page": 20})
        for h in snippet_hits(res, p["alt"], p["token"], p["cid"]):
            hits.setdefault(h["cluster_id"], h)
        if len(hits) >= 3:
            break
    ev["alt_citers"] = list(hits.values())
    bad = {}
    res = sy_call("search_cases", {"q": f'{p["token"]} w/15 "{p["ours"]}"', "compact": True, "per_page": 20})
    skip = {int(x) for x in p["other_cites"]}
    for h in snippet_hits(res, p["ours"], p["token"], p["cid"]):
        if h["cluster_id"] not in skip:
            bad.setdefault(h["cluster_id"], h)
    ev["ours_citers"] = list(bad.values())
    return ev


def run_evidence():
    """Strata in pool order; stop a stratum once it has its quota plus one spare of rows that pass evaluate()."""
    pool = jsonl(os.path.join(OUT, "pool.jsonl"))
    out, kept = [], {}
    want = {"A": PER_REP_A - 1 + 1, "C": PER_REP_C - 1 + 1}
    for i, p in enumerate(pool):
        key = (p["reporter"], p["klass"])
        if kept.get(key, 0) >= want[p["klass"]]:
            continue
        ev = gather(p)
        if evaluate(p, ev)[0]:
            kept[key] = kept.get(key, 0) + 1
        out.append(ev)
        print(f"{i+1}/{len(pool)} {p['cid']} {p['alt']} citers={len(ev['alt_citers'])} "
              f"ours_named={len(ev['ours_citers'])} cc={ev['check_citation']['verdict']}", flush=True)
    wjsonl(os.path.join(OUT, "evidence_raw.jsonl"), out)


# ---------------------------------------------------------------- controls

CONTROL_REPS = [("S.E.", 120), ("N.W.2d", 450), ("N.E.", 150), ("P.2d", 600), ("A.", 130), ("So. 2d", 700),
                ("S.W.", 250)]  # first and second series, so a control cannot be told from a trap by era


def control_pool():
    """Ordinary reported cases in the same reporters: 20-80 citing opinions, not in any fix ledger."""
    db = meta_db()
    touched = set()
    for src in (FIX_A, FIX_C, FIX_91):
        touched |= {int(r["cid"]) for r in jload(src)}
    for r in jsonl(os.path.join(LANES, "RESCORE166/x/neigh.jsonl")):
        touched.add(int(r["cid"]))
    touched |= used_clusters()
    out = []
    for rep, vol in CONTROL_REPS:
        vol = str(vol)
        rows = db.execute(
            "SELECT t.cluster_id, t.volume, t.page, c.case_name, c.date_filed, c.court_id, c.citation_count "
            "FROM citations t JOIN cases c ON c.cluster_id=t.cluster_id WHERE t.volume=? AND t.reporter=? "
            "AND c.citation_count BETWEEN 20 AND 80 ORDER BY t.page+0", (vol, rep)).fetchall()
        n = 0
        for cid, v, pg, name, filed, court, cnt in rows:
            if cid in touched or not name or not name_token(name) or len(holders(db, f"{v} {rep} {pg}")) != 1:
                continue
            out.append({"cid": cid, "cite": f"{v} {rep} {pg}", "reporter": rep, "case_name": name,
                        "date_filed": filed, "court_id": court, "citation_count": cnt, "token": name_token(name)})
            n += 1
            if n == 3:
                break
    return out


def run_controls():
    pool = control_pool()
    out = []
    for p in pool:
        cc = sy_call("check_citation", {"citation": p["cite"], "expected_case_name": p["case_name"]})
        js = (cc or {}).get("json") or {}
        m = (js.get("matches") or [{}])[0]
        res = sy_call("search_cases", {"q": f'{p["token"]} w/15 "{p["cite"]}"', "compact": True, "per_page": 20})
        hits = snippet_hits(res, p["cite"], p["token"], p["cid"])
        p.update({"check_citation": {"verdict": js.get("verdict"), "cluster_id": m.get("cluster_id"),
                                     "bluebook": m.get("bluebook"), "flag": (m.get("treatment") or {}).get("flag"),
                                     "name_check": (js.get("name_check") or {}).get("verdict")},
                  "citers": hits})
        out.append(p)
        print(p["cite"], p["case_name"][:40], js.get("verdict"), m.get("cluster_id") == p["cid"],
              (m.get("treatment") or {}).get("flag"), len(hits), flush=True)
    wjsonl(os.path.join(OUT, "controls_raw.jsonl"), out)


# ---------------------------------------------------------------- items

def date_strings(d):
    if not d or len(d) < 10:
        return []
    y, mo, da = int(d[:4]), int(d[5:7]), int(d[8:10])
    return [f"{MONTHS[mo-1]} {da}, {y}", f"{MON_AB[mo-1]} {da}, {y}", d]


def paren(bluebook):
    m = re.search(r"\(([^()]*\d{4})\)\s*$", bluebook or "")
    return m.group(1) if m else None


def year_fits(year, yrs, slack=1):
    return bool(yrs) and yrs[0] - slack <= year <= yrs[2] + slack


# Rows reviewed out by hand (2026-11-07): cluster id -> reason. Applied after the CourtListener step, like a CL drop, so item ids
# (and the saved CL replies keyed by them) never shift; the stratum's spare stands in.
EXCLUDE = {7445164: "reviewed out: CourtListener also places a second case (Western Union Tel. Co. v. Stokes) at the old "
                    "number 54 So. 181, so the item tests two things at once"}


def evaluate(p, ev):
    """-> (keep, why, facts)."""
    cc = ev["check_citation"]
    year = int((p["date_filed"] or "0")[:4] or 0)
    facts = {}
    if cc.get("cluster_id") != p["cid"]:
        return False, f"our MCP does not resolve {p['alt']} to {p['cid']} (got {cc.get('cluster_id')}, {cc.get('verdict')})", facts
    citers = [h for h in ev["alt_citers"] if (h.get("date_filed") or "9999") >= (p["date_filed"] or "")]
    if len(citers) < 2:
        return False, f"fewer than two citing opinions print {p['alt']} with '{p['token']}' ({len(citers)})", facts
    if ev["ours_citers"]:
        return False, (f"mixed: {len(ev['ours_citers'])} citing opinion(s) print the old number {p['ours']} "
                       f"with '{p['token']}'"), facts
    if not year_fits(year, p["alt_years"]):
        return False, f"decision year {year} outside the {p['alt']} volume span {p['alt_years']}", facts
    others = [h for h in p["alt_holders_meta"] if h != p["cid"]]
    if others:
        return False, f"another cluster sits at {p['alt']} in the meta ({others})", facts
    if re.search(r"&\d", p["case_name"] or ""):
        return False, f"garbled caption in the source ({p['case_name']!r})", facts
    facts["citers"] = citers
    facts["year_fit_alt"] = p["alt_years"]
    facts["year_fit_ours"] = year_fits(year, p["ours_years"])
    return True, "ok", facts


def clean_name(name):
    """CourtListener caption artifacts: 'State v. . Burnett' -> 'State v. Burnett'."""
    name = re.sub(r"\bv\.\s*\.\s*", "v. ", name or "")
    name = re.sub(r"^the people\b", "People", name, flags=re.I)
    name = re.sub(r"\bEx Rel\.", "ex rel.", name)
    return " ".join(name.split())


def build_item(p, ev, facts, shape, iid):
    cc = ev["check_citation"]
    bb = cc.get("bluebook") or ""
    case_name = clean_name(cc.get("case_name") or p["case_name"])
    pr = paren(bb)
    old_owner = None
    if p["klass"] == "C":
        oc = next(iter(p["other_names"].items()))
        old_owner = {"cluster_id": int(oc[0]), "case_name": oc[1][0], "date_filed": oc[1][1],
                     "cites": p["other_cites"][oc[0]]}
    cite_in_passage = p["alt"] if shape == "i" else p["ours"]
    text = f"{case_name}, {cite_in_passage}."
    if shape == "i":
        any_right = date_strings(p["date_filed"])
        if pr:
            any_right.append(f"({pr})")
            court = re.sub(r"\s*\d{4}$", "", pr).strip()
            if " " in court:  # an intermediate court ("Ga. Ct. App."), not the bare state ("Ga.")
                any_right.append(court)
        if cc.get("court"):  # the court's full name ("Supreme Court of Georgia") also counts as naming the court;
            any_right.append(cc["court"])  # the bare state ("Ga.") stays out: it is a substring of "Ga. Ct. App."
        dk = re.fullmatch(r"\[?(?:Docket\s*(?:No\.?)?\s*|No\.\s*)?([A-Z]?\d[\d\-]{3,})\.?\]?",
                          (p.get("docket_number") or "").strip())
        if dk:  # a bare docket number ("40679", "No. 42763"); captions like "L. A. No. 7442." are skipped
            any_right.append(dk.group(1))
        any_right = [a for a in any_right if grade.norm(a) not in grade.norm(text)]
        gold = {"right": [p["alt"]], "any_right": any_right, "absent": ABSENT_I, "wrong": [p["ours"]],
                "note": (f"real cite that the CourtListener index lacks (it holds {p['ours']} for this case); "
                         "the answer must add a fact not in the passage (date or court)")}
    else:
        gold = {"right": [p["alt"]], "wrong": [p["ours"]],
                "note": (f"{p['ours']} is the number CourtListener holds for this case; citing courts print "
                         f"{p['alt']}")}
        if old_owner:
            gold["note"] += (f". {p['ours']} is the first page of a different case, {old_owner['case_name']} "
                             f"({old_owner['date_filed']}, cluster {old_owner['cluster_id']})")
            gold["old_cite_owner"] = old_owner["case_name"]
    citers = facts["citers"]
    evidence = {
        "source": f"syfert.com MCP check_citation + search_cases, {TODAY}",
        "cluster_id": p["cid"],
        "bluebook": bb,
        "provenance": PROVENANCE,
        "fix_class": p["klass"], "fix_source": p["source"], "n_alt": p["n_alt"],
        "old_cl_cite": p["ours"], "printed_cite": p["alt"],
        "citing_opinions": [{"cluster_id": h["cluster_id"], "case": h["bluebook"], "date_filed": h["date_filed"],
                             "printed_as": h["printed_as"], "snippet": h["snippet"]} for h in citers[:4]],
        "date_check": (f"decided {p['date_filed']}; {p['alt']} volume spans {facts['year_fit_alt'][0]}-"
                       f"{facts['year_fit_alt'][2]} (p10-p90 of {facts['year_fit_alt'][3]} clusters in the "
                       f"CL-derived meta); {p['ours']} volume spans {p['ours_years'][0]}-{p['ours_years'][2]}"
                       if p.get("ours_years") else ""),
        "old_cite_printed_by_citers_with_this_name": 0,
    }
    if old_owner:
        evidence["old_cite_owner"] = old_owner
    return {"id": iid, "class": "regional", "shape": shape, "fix_class": p["klass"], "reporter": p["reporter"],
            "tool": "analyze_citations", "text": text, "gold": gold, "evidence": evidence, "version": VERSION}


def control_item(c, iid):
    cc = c["check_citation"]
    return {"id": iid, "class": "control", "kind": "control", "reporter": c["reporter"], "tool": "analyze_citations",
            "text": f"{clean_name(c['case_name'])}, {c['cite']}.",
            "gold": {"right": [c["cite"]], "absent": ABSENT_CONTROL,
                     "note": f"correct as written; {paren(cc.get('bluebook')) or ''}".strip()},
            "evidence": {"source": f"syfert.com MCP check_citation + search_cases, {TODAY}", "cluster_id": c["cid"],
                         "bluebook": cc.get("bluebook"), "flag": cc.get("flag"), "provenance": PROVENANCE,
                         "citing_opinions": [{"cluster_id": h["cluster_id"], "case": h["bluebook"],
                                              "date_filed": h["date_filed"], "snippet": h["snippet"]}
                                             for h in c["citers"][:3]],
                         "not_in_fix_ledgers": True},
            "version": VERSION}


SHORT = {"S.E.": "se", "S.E.2d": "se2", "N.W.": "nw", "N.W.2d": "nw2", "N.E.": "ne", "N.E.2d": "ne2", "P.": "p",
         "P.2d": "p2", "A.": "a", "A.2d": "a2", "So.": "so", "So. 2d": "so2", "S.W.": "sw", "S.W.2d": "sw2"}


def build_candidates():
    pool = {p["cid"]: p for p in jsonl(os.path.join(OUT, "pool.jsonl"))}
    evs = {e["cid"]: e for e in jsonl(os.path.join(OUT, "evidence_raw.jsonl"))}
    drops, items = [], []
    want = {"A": PER_REP_A - 1, "C": PER_REP_C - 1}  # ~2 A + ~1 C per reporter
    flip = 0
    for rep in REPORTERS:
        for klass in ("A", "C"):
            taken = 0
            for p in [x for x in pool.values() if x["reporter"] == rep and x["klass"] == klass]:
                ev = evs.get(p["cid"])
                if ev is None:
                    continue  # not reached: the stratum had its quota plus a spare before this row
                keep, why, facts = evaluate(p, ev)
                if not keep:
                    drops.append({"cid": p["cid"], "alt": p["alt"], "ours": p["ours"], "stage": "evidence", "why": why})
                    continue
                if taken >= want[klass] + 1:
                    continue  # quota plus one spare built; the spare stands in for a CourtListener drop
                shape = "i" if flip % 2 == 0 else "ii"
                flip += 1
                iid = f"rg-{SHORT[rep]}-{klass.lower()}{taken+1}"
                it = build_item(p, ev, facts, shape, iid)
                # echo hole: the passage must not contain the gold string it is graded on
                if shape == "ii" and grade.norm(p["alt"]) in grade.norm(it["text"]):
                    drops.append({"cid": p["cid"], "stage": "echo", "why": "passage contains the gold cite"})
                    continue
                if shape == "i" and not it["gold"]["any_right"]:
                    drops.append({"cid": p["cid"], "stage": "echo", "why": "no date/court fact outside the passage"})
                    continue
                it["_stratum"] = f"{rep}/{klass}"
                it["_quota"] = want[klass]
                items.append(it)
                taken += 1
    controls = [control_item(c, f"rg-co-{SHORT[c['reporter']]}")
                for c in pick_controls(jsonl(os.path.join(OUT, "controls_raw.jsonl")))]
    return items, controls, drops


def pick_controls(rows):
    out, seen = [], set()
    for c in rows:
        cc = c["check_citation"]
        if c["reporter"] in seen:
            continue
        if cc.get("cluster_id") == c["cid"] and cc.get("verdict") == "found" and cc.get("flag") == "green" \
                and cc.get("name_check") == "match" and len(c["citers"]) >= 2:
            out.append(c)
            seen.add(c["reporter"])
    return out


# ---------------------------------------------------------------- CourtListener (network)

def cl_body(iid):
    p = os.path.join(OUT, "cl", iid + ".txt")
    return open(p).read() if os.path.exists(p) else None


def run_cl(rows, cap):
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
        dest = os.path.join(d, row["id"] + ".txt")
        if os.path.exists(dest):
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
        with open(dest, "w") as f:
            f.write(body if body.endswith("\n") else body + "\n")
        print("cl", row["id"], body.splitlines()[-1][:100] if body.strip() else "", flush=True)
        if body.startswith("ERROR") and ("401" in body or "403" in body):
            raise SystemExit("CourtListener auth failure; stopping: " + body[:200])
    print("cl calls", calls)


def cl_verdict(row, body):
    """(drop, detail). Drop when the raw CL arm answers the item: grader pass, or the trap did not fire."""
    import score
    if body is None:
        return None, "no CL reply on disk"
    if body.startswith("ERROR"):
        return None, body[:160]
    g = grade.grade_item(body, row["gold"])
    parsed = score.parse(body)
    cases = parsed["cases"]
    st = cases[0]["status"] if cases else ("NONE" if "No citations found" in body else "?")
    cl_cid = cases[0]["cluster_id"] if cases else None
    warn = bool(cases and cases[0]["warning"])
    detail = f"status={st} cluster={cl_cid}" + (" name-warning" if warn else "") + f" grade={g['passed']}"
    if g["passed"]:
        return True, detail + " (grader passes the raw CL body)"
    if row.get("kind") == "control":
        return False, detail
    alt = row["gold"]["right"][0]
    if row["shape"] == "i":
        fired = st != "FOUND" or cl_cid != row["evidence"]["cluster_id"]
        return (not fired), detail + ("" if fired else " (CL resolves the printed cite to the case)")
    named = alt in body or undotted(alt) in body
    return named, detail + (" (CL names the corrected cite)" if named else "")


# ---------------------------------------------------------------- main

def self_checks(rows):
    bad = []
    for r in rows:
        ok, why = grade.self_check(r)
        if not ok:
            bad.append((r["id"], why))
    return bad


def main():
    global NETWORK
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", action="store_true")
    ap.add_argument("--pool", action="store_true")
    ap.add_argument("--evidence", action="store_true")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--cl", action="store_true")
    ap.add_argument("--max", type=int, default=120)
    a = ap.parse_args()
    NETWORK = a.network
    if (a.evidence or a.controls or a.cl) and not a.network:
        raise SystemExit("--evidence / --controls / --cl call the network; add --network")
    if a.pool:
        draw_pool()
        return
    if a.evidence:
        run_evidence()
        return
    if a.controls:
        run_controls()
        return
    items, controls, drops = build_candidates()
    wjsonl(os.path.join(OUT, "pre_cl.jsonl"), [{k: v for k, v in r.items() if not k.startswith("_")}
                                               for r in items + controls])
    if a.cl:
        run_cl(items + controls, a.max)
    final, cl_rows, spares, filled = [], [], [], {}
    for row in items + controls:
        body = cl_body(row["id"])
        drop, detail = cl_verdict(row, body)
        cl_rows.append({"id": row["id"], "text": row["text"], "cl": detail, "drop": drop})
        if drop is None:
            drops.append({"id": row["id"], "stage": "cl", "why": "not run: " + detail})
            continue
        if drop and row.get("kind") != "control":
            drops.append({"id": row["id"], "cid": row["evidence"]["cluster_id"], "text": row["text"], "stage": "cl",
                          "why": "raw CourtListener arm answers it: " + detail})
            continue
        if row.get("evidence", {}).get("cluster_id") in EXCLUDE:
            drops.append({"id": row["id"], "cid": row["evidence"]["cluster_id"], "text": row["text"], "stage": "review",
                          "why": EXCLUDE[row["evidence"]["cluster_id"]]})
            continue
        st = row.pop("_stratum", None)
        q = row.pop("_quota", None)
        if st is not None:
            if filled.get(st, 0) >= q:
                spares.append({"id": row["id"], "text": row["text"], "why": "spare; stratum full"})
                continue
            filled[st] = filled.get(st, 0) + 1
        row["evidence"]["courtlistener_raw"] = detail
        final.append(row)
    wjsonl(os.path.join(OUT, "spares.jsonl"), spares)
    bad = self_checks(final)
    wjsonl(ITEMS_OUT, final)
    wjsonl(os.path.join(OUT, "drops.jsonl"), drops)
    wjsonl(os.path.join(OUT, "cl_verdicts.jsonl"), cl_rows)
    from collections import Counter
    summ = {"items": len(final),
            "by_shape_class": dict(Counter(f"{r.get('shape','control')}/{r.get('fix_class','-')}" for r in final)),
            "by_reporter": dict(Counter(r["reporter"] for r in final)),
            "drops_by_stage": dict(Counter(d["stage"] for d in drops)),
            "self_check_failures": bad}
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump(summ, f, indent=1)
    print(json.dumps(summ, indent=1))


NETWORK = False

if __name__ == "__main__":
    main()
