# Build the v1.3 CANDIDATE wave ("wave 3") from the 2026-11-08 corrections: decision years (new class `date`) and a
# second batch of regional reporter numbers (class `regional`, ids rg3-*), plus date-shaped controls.
#
# usage:
#   python3 build_wave3.py --pool                      # draw the date, regional and control pools (offline)
#   python3 build_wave3.py --evidence --network        # Syfert MCP check_citation + search_cases per pool row
#   python3 build_wave3.py --cl --network [--max 100]  # raw CourtListener analyze_citations per candidate item
#   python3 build_wave3.py                             # offline: build items from what is on disk
#
# No network call is made unless --network is given. Every network reply is saved under OUT; the offline build reads
# only those files, the fix ledgers and caselaw_meta.db (opened read-only). Writes items/wave3.jsonl and
# OUT/{pool_*.jsonl,evidence_*.jsonl,pre_cl.jsonl,drops.jsonl,spares.jsonl,cl_verdicts.jsonl,summary.json}.
# It never touches items/tasks.jsonl, VERSION or CHANGELOG.md.
#
# Sources (read-only):
#   dates     DATE176/build/date_fix.tsv     (cluster_id, corrected date_filed, evidence line)
#             DATE151/x/date_ev2.jsonl       (votes = citer-printed years, ex = snippets, off = volume band)
#             DATE151/x/date_hold.json       (name, cite, stored date, corrected year)
#   regional  RESCORE166/fix/fixA2b.json     (class A, second batch)
#             RESCORE166/fix/fixC2.json      (class C, second batch: old number is another case's first page)
#             RESCORE166/x/names.json        (cid -> [case name, date, court])
#
# The regional half reuses build_regional.py's pool / evidence / evaluate / build_item code unchanged (same evidence
# standard); only the output directory, date, version and ids differ.
import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter

import build_regional as br
import grade

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "20261108-wave3")
LANES = br.LANES
DATE_FIX = os.path.join(LANES, "DATE176/build/date_fix.tsv")
DATE_EV = os.path.join(LANES, "DATE151/x/date_ev2.jsonl")
DATE_HOLD = os.path.join(LANES, "DATE151/x/date_hold.json")
FIX_A2 = os.path.join(LANES, "RESCORE166/fix/fixA2b.json")
FIX_C2 = os.path.join(LANES, "RESCORE166/fix/fixC2.json")
ITEMS_OUT = os.path.join(HERE, "items", "wave3.jsonl")
TODAY = "2026-11-08"
VERSION = "1.3-candidate"

# build_regional's helpers read these module globals; point them at this wave.
br.OUT = OUT
br.TODAY = TODAY
br.VERSION = VERSION

# --- quotas
DATE_NONMD = 10          # non-Maryland date traps
DATE_MD = 10             # Maryland date traps (247 of the 286 fixes are Maryland; capped so the class is not one court)
DATE_SPARE = 3           # spares per half, standing in for CourtListener drops
MD_DECADES = ["196", "197", "198", "199", "200"]  # stored-year decades; Maryland draw is spread over them
RG_A_REPS = ["S.E.", "S.E.2d", "N.W.", "N.W.2d", "N.E.", "N.E.2d", "P.", "P.2d", "A.", "So.", "S.W.", "S.W.2d"]
RG_C_REPS = ["N.E.2d", "S.E.2d", "N.W.", "P."]
RG_POOL_A = 3            # pool rows per reporter (1 kept + spares)
RG_POOL_C = 3
RG_QUOTA = {("P.", "A"): 2, ("So.", "A"): 2}  # the two reporters with the most class A rows; every other stratum 1
N_CONTROLS = 6

SKIP_REPORTERS = {"M.S.P.R."}  # MSPR rows carry a circuit / Supreme Court court id in CL: two errors at once
YEAR_RX = re.compile(r"\((?:[^()]{0,60}?\s)?((?:1[6-9]|20)\d\d)\)")
ABSENT_DATE = br.ABSENT_I + ["misprint", "typo", "interior page", "not the first page", "wrong reporter",
                             "wrong volume", "wrong page"]
# the controls' absent list, minus "should be" / "does not match", plus date words
ABSENT_CONTROL = br.ABSENT_CONTROL + ["wrong year", "wrong date", "year is incorrect", "date is incorrect"]
PROVENANCE = br.PROVENANCE
DATE_NOTE = ("Only the year was corrected; the month and day CourtListener holds are unverified, so no gold string "
             "contains a month or day.")
# casebook cases a bare model may date from memory: Perrin v. United States (1914), Escott v. BarChris (1968)
BARE_MODEL = {98104, 1906035}


def jload(p):
    with open(p) as f:
        return json.load(f)


jsonl = br.jsonl
wjsonl = br.wjsonl
parse_cite = br.parse_cite


def used_clusters():
    ids = br.used_clusters()
    for name in ("regional.jsonl",):
        for row in jsonl(os.path.join(HERE, "items", name)):
            e = row.get("evidence") or {}
            if e.get("cluster_id"):
                ids.add(int(e["cluster_id"]))
    return ids


def prior_regional_ledgers():
    s = set()
    for p in (br.FIX_A, br.FIX_C, br.FIX_91):
        s |= {int(r["cid"]) for r in jload(p)}
    return s


def cite_forms(cite):
    """Spellings a citing court prints: '126 A.2d 865', '126 A2d 865', '283 F.Supp. 643', '79 So.2d 233'."""
    forms = [cite]
    try:
        forms.append(br.undotted(cite))
    except Exception:
        pass
    sq = re.sub(r"\.\s+(?=[A-Za-z0-9])", ".", cite.split(" ", 1)[1].rsplit(" ", 1)[0])
    v, _, p = parse_cite(cite)
    forms.append(f"{v} {sq} {p}")
    return list(dict.fromkeys(forms))


# ---------------------------------------------------------------- date pool

def date_rows():
    hold = {r["cid"]: r for r in jload(DATE_HOLD)}
    ev = {}
    with open(DATE_EV) as f:
        for line in f:
            r = json.loads(line)
            ev[r["cid"]] = r
    out = []
    with open(DATE_FIX) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            cid = int(r["cluster_id"])
            h, e = hold[cid], ev[cid]
            out.append({"cid": cid, "case_name": h["name"], "hold_cite": h["cite"], "stored_date": e["date"],
                        "true_year": int(r["date_filed"][:4]), "fix_date": r["date_filed"], "court_id": e["court"],
                        "votes": e.get("votes") or {}, "ex": e.get("ex") or {}, "off": e.get("off") or [],
                        "n_votes": int(h.get("n") or 0), "fix_evidence": r["evidence"]})
    return out


REGIONAL_REP = re.compile(r"^(A|A\.2d|S\.E\.|S\.E\.2d|N\.E\.|N\.E\.2d|N\.W\.|N\.W\.2d|P\.|P\.2d|So\.|So\. 2d|S\.W\.|"
                          r"S\.W\.2d|U\.S\.|F\.|F\.2d|F\. Supp\.|F\.R\.D\.)$")


def pick_cite(r):
    """A national-reporter cite where the row has one, else the held cite."""
    cites = [c for c, _ in r["off"]] or [r["hold_cite"]]
    for c in cites:
        pc = parse_cite(c)
        if pc and REGIONAL_REP.match(pc[1]):
            return c
    return r["hold_cite"]


def draw_date_pool(db, used):
    rows = date_rows()
    pool = []
    nonmd = [r for r in rows if r["court_id"] != "md"]
    md = [r for r in rows if r["court_id"] == "md"]
    nonmd.sort(key=lambda r: (-r["n_votes"], r["cid"]))
    picked = []
    for r in nonmd:
        if r["cid"] in used or any(parse_cite(c)[1] in SKIP_REPORTERS for c, _ in r["off"] or [[r["hold_cite"], 0]]):
            continue
        if not br.name_token(r["case_name"]) or re.match(r"^opinion of the justices", r["case_name"], re.I):
            continue
        picked.append(r)
    # Maryland: per stored-year decade, the strongest rows by citer votes, then by citers.
    per = (DATE_MD + DATE_SPARE + len(MD_DECADES) - 1) // len(MD_DECADES) + 1
    for dec in MD_DECADES:
        cand = [r for r in md if r["stored_date"][:3] == dec and r["cid"] not in used and br.name_token(r["case_name"])]
        cand.sort(key=lambda r: (-r["n_votes"], r["cid"]))
        vols = set()
        k = 0
        for r in cand:
            c = pick_cite(r)
            vol = parse_cite(c)[0]
            if vol in vols:  # one per volume, so the Maryland items span the 1950s volumes
                continue
            vols.add(vol)
            picked.append(r)
            k += 1
            if k >= per:
                break
    for r in picked:
        cite = pick_cite(r)
        v, rep, _ = parse_cite(cite)
        pool.append(dict(r, cite=cite, reporter=rep, token=br.name_token(r["case_name"]),
                         other_cites=[c for c, _ in r["off"] if c != cite],
                         vol_years=br.volume_years(db, v, rep), holders_meta=br.holders(db, cite),
                         docket_number=br.case_meta(db, r["cid"]).get("docket_number")))
    return pool


# ---------------------------------------------------------------- regional pool (build_regional's method, new ledgers)

def draw_regional_pool(db, used):
    names = jload(br.NAMES)
    prior = prior_regional_ledgers()
    rows = [dict(r, klass="A", source="RESCORE166 fixA2b") for r in jload(FIX_A2)]
    rows += [dict(r, klass="C", source="RESCORE166 fixC2") for r in jload(FIX_C2)]
    pool = []
    plan = [(rep, "A", RG_POOL_A) for rep in RG_A_REPS] + [(rep, "C", RG_POOL_C) for rep in RG_C_REPS]
    for rep, klass, k in plan:
        cand = [r for r in rows if r["klass"] == klass and parse_cite(r["alt"])[1] == rep
                and parse_cite(r["ours"])[1] == rep and int(r["cid"]) not in used and int(r["cid"]) not in prior
                and int(parse_cite(r["ours"])[2]) > 0]
        # class C: one other case at the old number first (two or more tests two things at once)
        cand.sort(key=lambda r: (len(r.get("other_cites") or {}) > 1, -int(r.get("n_alt") or 0), int(r["cid"])))
        picked, decades = [], set()
        for passn in (0, 1):
            for r in cand:
                if len(picked) >= k or r in picked:
                    continue
                nm = names.get(str(r["cid"])) or [None, None, None]
                if not nm[0] or not br.name_token(nm[0]):
                    continue
                dec = (nm[1] or "????")[:3]
                if passn == 0 and dec in decades:
                    continue
                decades.add(dec)
                picked.append(r)
        for r in picked:
            nm = names.get(str(r["cid"]))
            cm = br.case_meta(db, r["cid"])
            pool.append({
                "cid": int(r["cid"]), "klass": klass, "reporter": rep, "ours": r["ours"], "alt": r["alt"],
                "n_alt": int(r.get("n_alt") or 0), "n_ours": r.get("n_ours"), "tier": None,
                "other_cites": r.get("other_cites") or {}, "source": r["source"],
                "case_name": nm[0], "date_filed": nm[1] or cm.get("date_filed"),
                "court_id": nm[2] or cm.get("court_id"), "docket_number": cm.get("docket_number"),
                "token": br.name_token(nm[0]),
                "alt_years": br.volume_years(db, *parse_cite(r["alt"])[:2]),
                "ours_years": br.volume_years(db, *parse_cite(r["ours"])[:2]),
                "alt_holders_meta": br.holders(db, r["alt"]),
                "other_names": {oc: (br.case_meta(db, oc).get("case_name"), br.case_meta(db, oc).get("date_filed"))
                                for oc in (r.get("other_cites") or {})},
            })
    return pool


# ---------------------------------------------------------------- control pool

CONTROL_VOLS = [("A.2d", "126", "md"), ("A.2d", "137", "md"), ("A.2d", "86", "md"), ("A.2d", "89", "pa"),
                ("N.W.2d", "163", "minn"), ("U.S.", "232", "scotus"), ("F. Supp.", "283", None),
                ("S.E.2d", "39", "va"), ("N.E.2d", "148", None)]


def draw_control_pool(db, used):
    """Ordinary reported cases in the same volumes as the date traps, not in any fix ledger or date-suspect list."""
    touched = set(used) | prior_regional_ledgers()
    for p in (FIX_A2, FIX_C2):
        touched |= {int(r["cid"]) for r in jload(p)}
    with open(DATE_EV) as f:
        touched |= {json.loads(x)["cid"] for x in f}  # every date suspect, not only the 286 fixes
    touched |= {r["cid"] for r in jload(DATE_HOLD)}
    for r in jsonl(os.path.join(LANES, "RESCORE166/x/neigh.jsonl")):
        touched.add(int(r["cid"]))
    out = []
    for rep, vol, court in CONTROL_VOLS:
        q = ("SELECT t.cluster_id, t.page, c.case_name, c.date_filed, c.court_id, c.citation_count FROM citations t "
             "JOIN cases c ON c.cluster_id=t.cluster_id WHERE t.volume=? AND t.reporter=? "
             "AND c.citation_count BETWEEN 15 AND 80" + (" AND c.court_id=?" if court else "") + " ORDER BY t.page+0")
        args = (vol, rep, court) if court else (vol, rep)
        yrs = br.volume_years(db, vol, rep)
        n = 0
        for cid, pg, name, filed, ct, cnt in db.execute(q, args).fetchall():
            cite = f"{vol} {rep} {pg}"
            if cid in touched or not name or not br.name_token(name) or len(br.holders(db, cite)) != 1:
                continue
            if not filed or not br.year_fits(int(filed[:4]), yrs, slack=0):
                continue
            out.append({"cid": cid, "cite": cite, "reporter": rep, "case_name": name, "date_filed": filed,
                        "court_id": ct, "citation_count": cnt, "token": br.name_token(name), "vol_years": yrs})
            n += 1
            if n == 2:
                break
    return out


def draw_pools():
    db = br.meta_db()
    used = used_clusters()
    os.makedirs(OUT, exist_ok=True)
    dp = draw_date_pool(db, used)
    rp = draw_regional_pool(db, used)
    cp = draw_control_pool(db, used | {p["cid"] for p in dp} | {p["cid"] for p in rp})
    wjsonl(os.path.join(OUT, "pool_date.jsonl"), dp)
    wjsonl(os.path.join(OUT, "pool_regional.jsonl"), rp)
    wjsonl(os.path.join(OUT, "pool_controls.jsonl"), cp)
    print("date pool", len(dp), Counter(p["court_id"] for p in dp).most_common())
    print("regional pool", len(rp), Counter((p["reporter"], p["klass"]) for p in rp))
    print("control pool", len(cp), Counter(p["reporter"] for p in cp))


# ---------------------------------------------------------------- date evidence

def date_hits(res, cite, token, self_cid):
    """Citing opinions whose snippet prints `cite` with `token` in the 160 chars before it, and the first year
    parenthetical within 120 chars after it (None when the snippet prints no year)."""
    out = []
    js = (res or {}).get("json") or {}
    for row in js.get("results") or []:
        cid = row.get("cluster_id")
        if cid == self_cid:
            continue
        snip = " ".join((row.get("snippet") or "").split())
        snip_n = re.sub(r"\s+,", ",", snip)
        for form in cite_forms(cite):
            m = re.search(r"(?<![\d])" + re.escape(form) + r"(?![\d])", snip_n)
            if not m:
                continue
            before = snip_n[max(0, m.start() - 160):m.start()]
            if token.lower() not in before.lower():
                continue
            after = snip_n[m.end():m.end() + 120]
            ym = YEAR_RX.search(after)
            # a year parenthetical that belongs to the next case in a string cite does not count
            if ym and re.search(r"\bv\.\s|;", after[:ym.start()]):
                ym = None
            out.append({"cluster_id": cid, "bluebook": row.get("bluebook"), "date_filed": row.get("date_filed"),
                        "printed_as": form, "printed_year": int(ym.group(1)) if ym else None, "snippet": snip})
            break
    return out


def gather_date(p):
    ev = {"cid": p["cid"]}
    cc = br.sy_call("check_citation", {"citation": p["cite"], "expected_case_name": p["case_name"]})
    js = (cc or {}).get("json") or {}
    m = (js.get("matches") or [{}])[0]
    ev["check_citation"] = {"verdict": js.get("verdict"), "cluster_id": m.get("cluster_id"),
                            "case_name": m.get("case_name"), "bluebook": m.get("bluebook"), "court": m.get("court"),
                            "date_filed": m.get("date_filed"), "flag": (m.get("treatment") or {}).get("flag"),
                            "name_check": (js.get("name_check") or {}).get("verdict")}
    hits = {}
    enough = lambda: sum(1 for h in hits.values() if h["printed_year"]) >= 4
    # the first distinctive party word; then, if that finds fewer than two, each party's surname
    # ('Lawrence E. Sexton v. Leopold Louis Dreyfus' is printed 'Sexton v. Dreyfus')
    for tok in name_tokens(p["case_name"], p["token"]):
        for c in [p["cite"]] + list(p.get("other_cites") or []):
            for form in cite_forms(c)[:2]:
                res = br.sy_call("search_cases", {"q": f'{tok} w/15 "{form}"', "compact": True, "per_page": 20})
                for h in date_hits(res, c, tok, p["cid"]):
                    hits.setdefault(h["cluster_id"], dict(h, token=tok))
                if enough():
                    break
            if enough():
                break
        if sum(1 for h in hits.values() if h["printed_year"]) >= 2:
            break
    ev["citers"] = list(hits.values())
    return ev


def name_tokens(name, first):
    out = [first]
    for party in re.split(r"\s+v\.?\s+|\s+vs\.?\s+", name or "", maxsplit=1):
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z'\-]+", party) if w.lower() not in br.GENERIC and len(w) >= 4]
        if words:
            out.append(words[-1])
    return list(dict.fromkeys(out))


def gather_control(p):
    return gather_date(dict(p, other_cites=[]))


def run_evidence():
    for name, fn in (("date", gather_date), ("controls", gather_control)):
        pool = jsonl(os.path.join(OUT, f"pool_{name}.jsonl"))
        out = []
        for i, p in enumerate(pool):
            ev = fn(p)
            out.append(ev)
            yrs = Counter(h["printed_year"] for h in ev["citers"])
            print(f"{name} {i+1}/{len(pool)} {p['cid']} {p.get('cite')} cc={ev['check_citation']['verdict']} "
                  f"bb={ev['check_citation']['bluebook']} years={dict(yrs)}", flush=True)
        wjsonl(os.path.join(OUT, f"evidence_{name}.jsonl"), out)
    # regional: build_regional.gather, stopping a stratum at quota + one spare that pass evaluate()
    pool = jsonl(os.path.join(OUT, "pool_regional.jsonl"))
    out, kept = [], Counter()
    for i, p in enumerate(pool):
        key = (p["reporter"], p["klass"])
        if kept[key] >= 2:
            continue
        ev = br.gather(p)
        if br.evaluate(p, ev)[0]:
            kept[key] += 1
        out.append(ev)
        print(f"regional {i+1}/{len(pool)} {p['cid']} {p['alt']} citers={len(ev['alt_citers'])} "
              f"ours_named={len(ev['ours_citers'])} cc={ev['check_citation']['verdict']}", flush=True)
    wjsonl(os.path.join(OUT, "evidence_regional.jsonl"), out)


# ---------------------------------------------------------------- date items

BB_RX = re.compile(r"^(?P<name>.*?), (?P<cite>\d+ [^,()]+? \d+)(?:, [^()]*)? \((?P<court>[^()]*?)\s*(?P<year>\d{4})\)\s*$")


def split_bluebook(bb):
    m = BB_RX.match(bb or "")
    return m.groupdict() if m else None


def evaluate_date(p, ev):
    cc = ev["check_citation"]
    ty = p["true_year"]
    sy = int(p["stored_date"][:4])
    facts = {}
    if cc.get("cluster_id") != p["cid"]:
        return False, f"our MCP does not resolve {p['cite']} to {p['cid']} (got {cc.get('cluster_id')})", facts
    bb = split_bluebook(cc.get("bluebook"))
    if not bb or int(bb["year"]) != ty:
        return False, f"our MCP bluebook does not carry the corrected year ({cc.get('bluebook')})", facts
    if bb["cite"] != p["cite"]:
        return False, f"our MCP bluebook leads with another cite ({bb['cite']})", facts
    if cc.get("name_check") not in ("match", None):
        return False, f"name check {cc.get('name_check')}", facts
    good = [h for h in ev["citers"] if h["printed_year"] == ty]
    bad = [h for h in ev["citers"] if h["printed_year"] == sy]
    other = [h for h in ev["citers"] if h["printed_year"] not in (None, ty, sy)]
    if len(good) < 2:
        return False, f"fewer than two citing snippets name the case and print {ty} ({len(good)})", facts
    if bad:
        return False, f"mixed: {len(bad)} citing snippet(s) print the stored year {sy}", facts
    if len(other) > len(good) // 2:
        return False, f"{len(other)} citing snippets print a third year ({[h['printed_year'] for h in other]})", facts
    vy = p.get("vol_years")
    if not br.year_fits(ty, vy, slack=1):
        return False, f"corrected year {ty} outside the volume span {vy}", facts
    if vy[0] - 5 <= sy <= vy[2] + 5:
        return False, f"stored year {sy} is within 5 years of the volume span {vy}", facts
    others = [h for h in p["holders_meta"] if h != p["cid"]]
    if others:
        return False, f"another cluster sits at {p['cite']} in the meta ({others})", facts
    for y in (str(ty), str(sy)):
        if y in p["cite"] or y in bb["name"]:
            return False, f"year string {y} occurs in the cite or the name", facts
    facts.update(good=good, other=other, bb=bb, predate=[h for h in ev["citers"]
                                                         if (h.get("date_filed") or "9999")[:4] < str(sy)])
    return True, "ok", facts


def date_item(p, ev, facts, shape, iid):
    bb = facts["bb"]
    ty, sy = p["true_year"], int(p["stored_date"][:4])
    court = bb["court"].strip()
    year = ty if shape == "i" else sy
    text = f"{br.clean_name(bb['name'])}, {p['cite']} ({court + ' ' if court else ''}{year})."
    gold = {"right": [p["cite"]], "any_of": [str(ty)], "verdict_line": True, "wrong": [str(sy)],
            "absent": ABSENT_DATE}
    if shape == "i":
        gold["note"] = (f"correct as written: decided {ty}. CourtListener stores {p['stored_date']} for this case, "
                        f"so a checker that trusts it 'corrects' the year to {sy}. The ANSWER line must carry {ty} "
                        f"and not {sy}. " + DATE_NOTE)
    else:
        gold["note"] = (f"{sy} is the year CourtListener stores ({p['stored_date']}); the case was decided in {ty}, "
                        f"the year citing courts print and the era of the volume. The ANSWER line must carry {ty} "
                        f"and not {sy}. " + DATE_NOTE)
    vy = p["vol_years"]
    good = facts["good"]
    evidence = {
        "source": f"syfert.com MCP check_citation + search_cases, {TODAY}",
        "cluster_id": p["cid"],
        "bluebook": ev["check_citation"]["bluebook"],
        "provenance": PROVENANCE,
        "fix_source": "DATE176 date_fix.tsv",
        "fix_evidence": p["fix_evidence"],
        "stored_cl_date": p["stored_date"],
        "corrected_year": ty,
        "month_day": "unverified (CourtListener's month and day kept; only the year was corrected)",
        "date151_votes": p["votes"],
        "date151_example": p["ex"].get(str(ty)),
        "volume_band": p["off"],
        "volume_check": (f"{p['cite']}: decisions in this volume span {vy[0]}-{vy[2]} (p10-p90 of {vy[3]} clusters "
                         f"in the CL-derived meta); stored year {sy} is {min(abs(sy - vy[0]), abs(sy - vy[2]))} "
                         f"years outside it"),
        "citing_opinions": [{"cluster_id": h["cluster_id"], "case": h["bluebook"], "date_filed": h["date_filed"],
                             "printed_as": h["printed_as"], "printed_year": h["printed_year"], "snippet": h["snippet"]}
                            for h in good[:4]],
        "citing_snippets_printing_stored_year": 0,
        "citing_snippets_printing_a_third_year": [{"cluster_id": h["cluster_id"], "printed_year": h["printed_year"]}
                                                  for h in facts["other"]],
        "citers_dated_before_stored_year": len(facts["predate"]),
    }
    famous = p["cid"] in BARE_MODEL
    it = {"id": iid, "class": "date", "shape": shape, "court_id": p["court_id"], "reporter": p["reporter"],
          "tool": "analyze_citations", "text": text, "gold": gold, "evidence": evidence, "version": VERSION}
    if famous:
        it["bare_model_answerable"] = True
    return it


def build_date_items(drops):
    pool = jsonl(os.path.join(OUT, "pool_date.jsonl"))
    evs = {e["cid"]: e for e in jsonl(os.path.join(OUT, "evidence_date.jsonl"))}
    halves = {"nonmd": [], "md": []}
    for p in pool:
        ev = evs.get(p["cid"])
        if ev is None:
            continue
        keep, why, facts = evaluate_date(p, ev)
        if not keep:
            drops.append({"cid": p["cid"], "cite": p["cite"], "name": p["case_name"], "stage": "evidence",
                          "class": "date", "why": why})
            continue
        halves["md" if p["court_id"] == "md" else "nonmd"].append((p, ev, facts))
    items = []
    for half, quota in (("nonmd", DATE_NONMD), ("md", DATE_MD)):
        rows = halves[half]
        if half == "md":
            # round-robin over stored-year decades, strongest first
            by = {d: [r for r in rows if r[0]["stored_date"][:3] == d] for d in MD_DECADES}
            rows = []
            while any(by.values()):
                for d in MD_DECADES:
                    if by[d]:
                        rows.append(by[d].pop(0))
        n = Counter()
        for k, (p, ev, facts) in enumerate(rows[:quota + DATE_SPARE]):
            shape = "i" if k % 2 == 0 else "ii"
            ct = re.sub(r"[^a-z0-9]", "", p["court_id"])
            n[ct] += 1
            iid = f"dt-{ct}-{n[ct]}"
            it = date_item(p, ev, facts, shape, iid)
            if shape == "ii" and grade.norm(str(p["true_year"])) in grade.norm(it["text"]):
                drops.append({"cid": p["cid"], "stage": "echo", "why": "shape (ii) passage contains the gold year"})
                continue
            it["_stratum"] = f"date/{half}"
            it["_quota"] = quota
            items.append(it)
    return items


def regional_items(drops):
    pool = {p["cid"]: p for p in jsonl(os.path.join(OUT, "pool_regional.jsonl"))}
    evs = {e["cid"]: e for e in jsonl(os.path.join(OUT, "evidence_regional.jsonl"))}
    items = []
    plan = [(rep, "A") for rep in RG_A_REPS] + [(rep, "C") for rep in RG_C_REPS]
    for si, (rep, klass) in enumerate(plan):
        quota = RG_QUOTA.get((rep, klass), 1)
        taken = 0
        for p in [x for x in pool.values() if x["reporter"] == rep and x["klass"] == klass]:
            ev = evs.get(p["cid"])
            if ev is None:
                continue
            keep, why, facts = br.evaluate(p, ev)
            if not keep:
                drops.append({"cid": p["cid"], "alt": p["alt"], "ours": p["ours"], "stage": "evidence",
                              "class": "regional", "why": why})
                continue
            if taken >= quota + 1:  # quota + one spare per stratum
                continue
            # shapes alternate by stratum, so the kept rows (the first of each stratum) are balanced too
            shape = "i" if (si + taken) % 2 == 0 else "ii"
            iid = f"rg3-{br.SHORT[rep]}-{klass.lower()}{taken+1}"
            it = br.build_item(p, ev, facts, shape, iid)
            it["evidence"]["fix_source"] = p["source"]
            if shape == "ii" and grade.norm(p["alt"]) in grade.norm(it["text"]):
                drops.append({"cid": p["cid"], "stage": "echo", "why": "passage contains the gold cite"})
                continue
            if shape == "i" and not it["gold"]["any_right"]:
                drops.append({"cid": p["cid"], "stage": "echo", "why": "no date/court fact outside the passage"})
                continue
            it["_stratum"] = f"{rep}/{klass}"
            it["_quota"] = quota
            items.append(it)
            taken += 1
    return items


def control_items(drops):
    pool = jsonl(os.path.join(OUT, "pool_controls.jsonl"))
    evs = {e["cid"]: e for e in jsonl(os.path.join(OUT, "evidence_controls.jsonl"))}
    out, md, other, vols = [], 0, 0, set()
    for p in pool:
        ev = evs.get(p["cid"])
        if ev is None:
            continue
        cc = ev["check_citation"]
        bb = split_bluebook(cc.get("bluebook"))
        y = int(p["date_filed"][:4])
        good = [h for h in ev["citers"] if h["printed_year"] == y]
        badc = [h for h in ev["citers"] if h["printed_year"] not in (None, y)]
        why = None
        if cc.get("cluster_id") != p["cid"] or cc.get("verdict") != "found":
            why = f"MCP does not resolve it ({cc.get('cluster_id')}, {cc.get('verdict')})"
        elif cc.get("flag") != "green" or cc.get("name_check") != "match":
            why = f"flag {cc.get('flag')} / name {cc.get('name_check')}"
        elif not bb or int(bb["year"]) != y or bb["cite"] != p["cite"]:
            why = f"bluebook {cc.get('bluebook')}"
        elif len(good) < 2 or badc:
            why = f"year evidence: {len(good)} print {y}, {len(badc)} print another year"
        elif str(y) in p["cite"]:
            why = "year string in the cite"
        if why:
            drops.append({"cid": p["cid"], "cite": p["cite"], "stage": "evidence", "class": "control", "why": why})
            continue
        vol = (p["reporter"], parse_cite(p["cite"])[0])
        if vol in vols:
            continue
        is_md = p["court_id"] == "md"
        if (is_md and md >= N_CONTROLS // 2) or (not is_md and other >= N_CONTROLS - N_CONTROLS // 2):
            continue
        vols.add(vol)
        md += is_md
        other += not is_md
        court = bb["court"].strip()
        iid = f"dt-co-{len(out)+1}"
        out.append({"id": iid, "class": "control", "kind": "control", "reporter": p["reporter"],
                    "court_id": p["court_id"], "tool": "analyze_citations",
                    "text": f"{br.clean_name(bb['name'])}, {p['cite']} ({court + ' ' if court else ''}{y}).",
                    "gold": {"right": [p["cite"]], "any_of": [str(y)], "verdict_line": True,
                             "absent": ABSENT_CONTROL, "note": f"correct as written, year included ({y})"},
                    "evidence": {"source": f"syfert.com MCP check_citation + search_cases, {TODAY}",
                                 "cluster_id": p["cid"], "bluebook": cc.get("bluebook"), "flag": cc.get("flag"),
                                 "provenance": PROVENANCE,
                                 "volume_check": f"{p['cite']} volume spans {p['vol_years'][0]}-{p['vol_years'][2]}",
                                 "citing_opinions": [{"cluster_id": h["cluster_id"], "case": h["bluebook"],
                                                      "date_filed": h["date_filed"], "printed_year": h["printed_year"],
                                                      "snippet": h["snippet"]} for h in good[:3]],
                                 "not_in_fix_ledgers": True, "not_in_date_suspects": True},
                    "version": VERSION})
    return out


# ---------------------------------------------------------------- CourtListener

CL_DATE_RX = re.compile(r"^\s+1\. .*? — .*\((\d{4})-\d\d-\d\d\)\s*$", re.M)


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
        if cl_body(row) is not None:
            continue
        if os.path.exists(dest):  # reply to an earlier passage under this id: keep it under stale/
            os.makedirs(os.path.join(d, "stale"), exist_ok=True)
            for ext in (".txt", ".in"):
                src = os.path.join(d, row["id"] + ext)
                if os.path.exists(src):
                    os.replace(src, os.path.join(d, "stale", row["id"] + ext))
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
        with open(os.path.join(d, row["id"] + ".in"), "w") as f:
            f.write(row["text"] + "\n")
        print("cl", row["id"], (body.strip().splitlines() or [""])[-1][:100], flush=True)
        if body.startswith("ERROR") and ("401" in body or "403" in body):
            raise SystemExit("CourtListener auth failure; stopping: " + body[:200])
    print("cl calls", calls)


def cl_body(row):
    """The saved CL reply for this id, only if it was the reply to this exact passage."""
    base = os.path.join(OUT, "cl", row["id"])
    if not (os.path.exists(base + ".txt") and os.path.exists(base + ".in")):
        return None
    if open(base + ".in").read().strip() != row["text"].strip():
        return None
    return open(base + ".txt").read()


def cl_verdict(row, body):
    """(drop, detail). Drop when the raw CL arm answers the item: grader pass, or the trap did not fire."""
    import score
    if body is None:
        return None, "no CL reply on disk"
    if body.startswith("ERROR"):
        return None, body[:160]
    g = grade.grade_item(body, row["gold"], row["text"])
    cases = score.parse(body)["cases"]
    st = cases[0]["status"] if cases else ("NONE" if "No citations found" in body else "?")
    cl_cid = cases[0]["cluster_id"] if cases else None
    dm = CL_DATE_RX.search(body)
    cl_year = int(dm.group(1)) if dm else None
    detail = f"status={st} cluster={cl_cid} cl_year={cl_year} grade={g['passed']}"
    if g["passed"]:
        return (row.get("kind") != "control"), detail + " (grader passes the raw CL body)"
    if row.get("kind") == "control":
        return False, detail
    if row["class"] == "date":
        ty = row["evidence"]["corrected_year"]
        if cl_year == ty:
            return True, detail + " (CL already shows the corrected year)"
        return False, detail
    return br.cl_verdict(row, body)


# ---------------------------------------------------------------- main

def build(run_cl_step, cap):
    drops = []
    items = build_date_items(drops) + regional_items(drops)
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
                          "why": "raw CourtListener arm answers it: " + detail})
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
            "date_by_court": dict(Counter(r["court_id"] for r in final if r["class"] == "date")),
            "regional_by_reporter": dict(Counter(r["reporter"] for r in final if r["class"] == "regional")),
            "drops_by_stage": dict(Counter(f"{d['stage']}/{d.get('class', '')}" for d in drops)),
            "self_check_failures": bad}
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump(summ, f, indent=1)
    print(json.dumps(summ, indent=1))


# Rows reviewed out by hand: cluster id -> reason. Applied after the CourtListener step (ids never shift).
EXCLUDE = {4232650: "reviewed out: the citers quoted print 22 N.W.2d 657 for In re Sweeney's Estate, 248 Wis. 607; "
                    "CourtListener's 24 N.W.2d 406 is a different volume and page, so this may be a separate opinion "
                    "(rehearing) rather than a misnumbered one"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", action="store_true")
    ap.add_argument("--pool", action="store_true")
    ap.add_argument("--evidence", action="store_true")
    ap.add_argument("--cl", action="store_true")
    ap.add_argument("--max", type=int, default=100)
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
