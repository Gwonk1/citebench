# usage: imported by grade.py; standalone check: python3 reconcile.py "So. 3d" 346
"""Reconcile check_brief's UNRESOLVED cites against the corpus before calling them fabricated.

Why: the reporter index behind check_brief/check_citation (citations_by_cluster) stops paginating
So. 3d around vol 275 (~2019) and is thin on F. App'x, so real 2020+ opinions come back cluster_id null.
The opinions themselves ARE in the corpus (search_cases finds them by name).

For each unresolved cite, in order (first accepting route wins; every attempt is logged as evidence):
  1. check_citation(citation, expected_case_name)  -> accept a match / name candidate that passes the
     name + year tests below.
  2. search_cases(q = the distinctive party words, each quoted, then q = name:<first distinctive party word>; scoped by the parenthetical court,
     else the question's state; retried unscoped) -> accept a hit that passes the tests.
  3. (always run) search_cases(q = the exact citation string in quotes) -> accept when another court's opinion snippet
     contains that exact cite next to the claimed party name (courts citing it that way = the cite exists,
     page included). The cited case's own cluster is then looked up by name as in 2 when possible.
Tests for routes 1-2:
  * name: both sides fuzzy-match (tokens lower-cased, punctuation and noise words such as v./vs./inc./
    corp./llc/the dropped; every distinctive token on the shorter side must appear, with difflib ratio
    >= 0.85, on the other). Names with no " v. " (In re, Advisory Opinion ...): >= 70% of the claimed
    distinctive tokens appear in the hit's name.
  * year: the hit's decision year lies inside the year band of the cite's reporter volume (below), and
    within +-1 of the year the answer put in the parenthetical, when it gave one (EXACT year when one side is
    a generic party such as State/People/Commonwealth/United States, where surnames collide);
  * court: Florida (Fla. vs DCA) and federal-circuit parentheticals must match the hit court level;
  * cite: if the hit already carries a cite in the SAME reporter with a different volume/page, the model
    miscited a real case -> stays fabricated (evidence kept as miscited_real_case).
Year band per (reporter, volume): from the corpus, read-only. Take up to 400 clusters citing that volume in
citations_by_cluster, look their date_filed up in cases_lite, band = [p10 - 1, p90 + 1]. For a volume past
the end of the index, find the last DENSE indexed volume (>= 20 cites, probing downward), fit years-per-volume by least
squares over the median years of up to 5 anchor volumes spaced 25 apart below it, extrapolate, band =
prediction +-1.5 years (slope floored at 0). Bands are cached in results/reporter_years.json.
"""
import difflib
import json
import math
import os
import re
import sqlite3
import statistics
import sys
import threading

CBC_DB = "/var/www/caselaw/cache/citations_by_cluster.db"
CASES_DB = "/var/www/caselaw/cache/cases_lite.db"
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "reporter_years.json")
_lock = threading.Lock()
_cache = None

NOISE = {"v", "vs", "versus", "inc", "corp", "corporation", "co", "company", "llc", "ltd", "lp", "llp", "pa",
         "the", "of", "a", "an", "and", "et", "al", "re", "in", "ex", "rel", "for", "to", "on", "at", "by"}
GENERIC = {"state", "united", "states", "people", "commonwealth", "city", "county", "florida", "america",
           "department", "dept", "board", "town", "village", "school", "district", "government", "us", "usa"}

HISTORY_WORDS = {"review", "denied", "later", "cert", "certiorari", "granted", "dismissed", "affd", "affirmed",
                 "rev", "reh", "rehearing", "see", "also", "held", "court", "case"}
STATE_ABBR = {
    "Ala.": "al", "Alaska": "ak", "Ariz.": "az", "Ark.": "ar", "Cal.": "ca", "Colo.": "co", "Conn.": "ct",
    "Del.": "de", "D.C.": "dc", "Fla.": "fl", "Ga.": "ga", "Haw.": "hi", "Idaho": "id", "Ill.": "il",
    "Ind.": "in", "Iowa": "ia", "Kan.": "ks", "Ky.": "ky", "La.": "la", "Me.": "me", "Md.": "md",
    "Mass.": "ma", "Mich.": "mi", "Minn.": "mn", "Miss.": "ms", "Mo.": "mo", "Mont.": "mt", "Neb.": "ne",
    "Nev.": "nv", "N.H.": "nh", "N.J.": "nj", "N.M.": "nm", "N.Y.": "ny", "N.C.": "nc", "N.D.": "nd",
    "Ohio": "oh", "Okla.": "ok", "Or.": "or", "Pa.": "pa", "R.I.": "ri", "S.C.": "sc", "S.D.": "sd",
    "Tenn.": "tn", "Tex.": "tx", "Utah": "ut", "Vt.": "vt", "Va.": "va", "Wash.": "wa", "W. Va.": "wv",
    "Wis.": "wi", "Wyo.": "wy"}


# ------------------------------------------------------------------ year bands (read-only corpus)
def _ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)


def _vol_years(cbc, cases, reporter, volume, limit=400, frac=False):
    ids = [r[0] for r in cbc.execute(
        "SELECT cluster_id FROM citations WHERE volume=? AND reporter=? LIMIT ?", (str(volume), reporter, limit))]
    if not ids:
        return []
    ys = []
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        q = "SELECT date_filed FROM cases_lite WHERE cluster_id IN (%s)" % ",".join("?" * len(chunk))
        for (d,) in cases.execute(q, chunk):
            if d and d[:4].isdigit():
                if frac and len(d) >= 7 and d[5:7].isdigit():
                    ys.append(int(d[:4]) + (int(d[5:7]) - 0.5) / 12)
                else:
                    ys.append(int(d[:4]))
    return sorted(ys)


def _pct(ys, p):
    return ys[min(len(ys) - 1, max(0, int(round(p * (len(ys) - 1)))))]


def year_band(reporter, volume):
    """-> dict(lo, hi, method, detail) or None if the corpus DBs are unavailable."""
    global _cache
    try:
        volume = int(volume)
    except (TypeError, ValueError):
        return None
    key = f"{reporter}|{volume}"
    with _lock:
        if _cache is None:
            try:
                _cache = json.load(open(CACHE_PATH))
            except Exception:
                _cache = {}
        if key in _cache:
            return _cache[key]
    if not (os.path.exists(CBC_DB) and os.path.exists(CASES_DB)):
        return None
    cbc, cases = _ro(CBC_DB), _ro(CASES_DB)
    try:
        ys = _vol_years(cbc, cases, reporter, volume)
        if len(ys) >= 5:
            band = {"lo": _pct(ys, 0.10) - 1, "hi": _pct(ys, 0.90) + 1, "method": "indexed",
                    "detail": f"{len(ys)} clusters, p10={_pct(ys, .1)} p90={_pct(ys, .9)}"}
        else:
            band = None
            dense = None
            for v in range(volume - 1, max(0, volume - 600), -1):
                n = len(cbc.execute("SELECT 1 FROM citations WHERE volume=? AND reporter=? LIMIT 20",
                                    (str(v), reporter)).fetchall())
                if n >= 20:
                    dense = v
                    break
            if dense:
                pts = []
                for v in range(dense, max(0, dense - 101), -25):
                    vy = _vol_years(cbc, cases, reporter, v, 300, frac=True)
                    if len(vy) >= 5:
                        pts.append((v, round(statistics.median(vy), 2)))
                if len(pts) >= 2:
                    mx = statistics.mean(p[0] for p in pts)
                    my = statistics.mean(p[1] for p in pts)
                    sxx = sum((p[0] - mx) ** 2 for p in pts)
                    slope = max(0.0, sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx) if sxx else 0.0
                    pred = my + slope * (volume - mx)
                    band = {"lo": math.floor(pred - 1.5), "hi": math.ceil(pred + 1.5),
                            "method": "extrapolated",
                            "detail": f"last dense vol {dense}; anchors {pts}; {slope:.4f} yr/vol; pred {pred:.2f}"}
                elif pts:
                    band = {"lo": int(pts[0][1]), "hi": 9999, "method": "floor_only",
                            "detail": f"last dense vol {dense} median {pts[0][1]}"}
    finally:
        cbc.close()
        cases.close()
    with _lock:
        _cache[key] = band
        try:
            tmp = CACHE_PATH + ".tmp"
            json.dump(_cache, open(tmp, "w"), indent=1)
            os.replace(tmp, CACHE_PATH)
        except Exception:
            pass
    return band


# ------------------------------------------------------------------ names
def _toks(s):
    s = (s or "").lower().replace("’", "'")
    s = re.sub(r"'s\b", "", s)
    return [t for t in re.sub(r"[^a-z0-9]+", " ", s).split() if t not in NOISE]


def _split_sides(name):
    parts = re.split(r"\s+(?:v\.|vs\.?|versus|v)\s*(?=[A-Z0-9])", name or "", maxsplit=1)
    return (parts[0], parts[1]) if len(parts) == 2 else (name, None)


def _tok_in(t, pool):
    return any(t == p or (len(t) > 3 and difflib.SequenceMatcher(None, t, p).ratio() >= 0.85) for p in pool)


def _side_match(a, b):
    ta, tb = _toks(a), _toks(b)
    if not ta or not tb:
        return False
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return all(_tok_in(t, long_) for t in short)


def name_match(claimed, hit_name):
    cl, cr = _split_sides(claimed)
    hl, hr = _split_sides(hit_name)
    if cr is not None and hr is not None:
        return (_side_match(cl, hl) and _side_match(cr, hr)) or (_side_match(cl, hr) and _side_match(cr, hl))
    ct = [t for t in _toks(claimed) if len(t) > 2 or t.isdigit()]
    ht = _toks(hit_name)
    if not ct or not ht:
        return False
    nums = [t for t in re.findall(r"\d+(?:\.\d+)?", claimed or "")]
    if any(n not in (hit_name or "") for n in nums):
        return False          # 'Rule 1.510' must not match 'Rule 1.280'
    return sum(_tok_in(t, ht) for t in ct) / len(ct) >= 0.7


def distinctive_words(claimed):
    if _split_sides(claimed)[1] is None:   # In re / Advisory Opinion ...: up to 4 distinctive words
        ts = [t for t in _toks(claimed) if len(t) > 2 and t not in GENERIC]
        return ts[:4]
    words = []
    for side in _split_sides(claimed):
        if not side:
            continue
        ts = [t for t in _toks(side) if len(t) > 2]
        dist = [t for t in ts if t not in GENERIC]
        if dist:
            words.extend(dist[:2])
        elif ts:
            words.append(" ".join(ts))  # "united states" stays one quoted phrase
    return words[:4]


# ------------------------------------------------------------------ answer parsing
def char_offsets(text, cite):
    """check_brief offsets are UTF-8 BYTE offsets (observed 2026-09-22: they drift right of the cite by
    one char per multi-byte char before it). Convert to str indices, verifying against the raw cite."""
    raw = cite.get("raw") or ""
    b = text.encode("utf-8")
    out = []
    for off in cite.get("offsets") or []:
        if text[off:off + len(raw)] == raw:
            out.append(off)
            continue
        ci = len(b[:off].decode("utf-8", errors="ignore"))
        if text[ci:ci + len(raw)] == raw:
            out.append(ci)
            continue
        j = text.find(raw, max(0, ci - 50))
        out.append(j if j >= 0 else ci)
    return out


PAREN_RE = re.compile(r"^[^()]{0,40}?\(([^()]*?)(\d{4})\)")
SIGNAL_RE = re.compile(r"^(?:see,?(?: also| generally)?,?|e\.g\.,?|cf\.,?|accord,?|but see,?|in|under|citing|"
                       r"quoting|the court in|as held in|and|also|compare|with)\s+", re.I)


ABBR = {"assocs", "assn", "corp", "dept", "bros", "univ", "natl", "intl", "mgmt", "prop", "props", "ins",
        "servs", "sys", "fla", "cnty", "twp", "gov", "comm", "commn", "hosp", "elec", "coop", "mfg", "auth"}


def _last_clause(pre):
    """Text after the last sentence/clause boundary. A period only ends a sentence when the word before it
    is longer than 3 letters and not a reporter/case-name abbreviation (so 'v.', 'Inc.', 'Assocs.' don't)."""
    cut = 0
    for m in re.finditer(r"[;!?\n\u2014]|\)\s*[,;]?\s|:\s(?=[A-Z])", pre):
        if m.group(0).startswith(":") and re.search(r"\bre$", pre[:m.start()], re.I):
            continue
        cut = max(cut, m.end())
    for m in re.finditer(r"(\w+)\.\s+(?=[A-Z])", pre):
        w = m.group(1)
        if len(w) > 3 and w.lower() not in ABBR:
            cut = max(cut, m.end())
    return pre[cut:]


CONNECT = {"of", "the", "for", "a", "an", "and", "&", "de", "ex", "rel.", "rel", "in", "re", "re:", "on", "to"}


def _tidy_name(s):
    """Trim prose before a case name: keep the run of Capitalised words / connectors that ends at ' v. '."""
    s = (s or "").strip().rstrip(",").strip()
    for _ in range(3):
        s = SIGNAL_RE.sub("", s).strip()
    m = re.search(r"\s(?:v\.|vs\.?)\s", s)
    if not m:
        starts = list(re.finditer(r"\b(?:In re|Ex parte|In the Matter of|Matter of|Advisory Opinion|Petition of|"
                                  r"Estate of|Application of)\b", s, re.I))
        if starts:
            return s[starts[-1].start():]
        words = s.split()
        keep = []
        for w in reversed(words):
            if w[:1].isupper() or w[:1].isdigit() or w.lower() in CONNECT:
                keep.append(w)
            else:
                break
        return " ".join(reversed(keep)) or s
    words = s[:m.start()].split()
    keep = []
    for w in reversed(words):
        if w[:1].isupper() or w[:1].isdigit() or w.lower() in CONNECT or w[:1] in "'\u2019(":
            keep.append(w)
            if w.endswith(".") and len(w.rstrip(".")) > 3 and w.rstrip(".").lower() not in ABBR and len(keep) > 1:
                keep.pop()          # 'Jimenez.' = end of the previous sentence
                break
        else:
            break
    while keep and keep[-1].lower() in CONNECT:
        keep.pop()
    lhs = " ".join(reversed(keep)) or s[:m.start()]
    return f"{lhs} v. {s[m.end():].strip()}"


def claimed_name(cite, answer, use_claimed=True):
    """Case name the answer attached to this cite: check_brief's claimed parties when present (unless
    use_claimed=False), else the text immediately before the cite."""
    cl = cite.get("claimed") or {}
    if use_claimed and cl.get("lhs") and cl.get("rhs"):
        return _tidy_name(f"{cl['lhs']} v. {cl['rhs']}")
    offs = char_offsets(answer, cite)
    if not offs:
        return None
    pre = answer[max(0, offs[0] - 200):offs[0]]
    pre = re.sub(r"\s*\((?:[^()]*\s)?\d{4}\)\s*$", " ", pre)   # California style: Name (2021) 11 Cal.5th 614
    pre = _tidy_name(_last_clause(pre))
    if SUBSEQ_RE.search(pre + ","):
        return None
    return pre if len(_toks(pre)) >= 1 else None


SUBSEQ_RE = re.compile(r"(?:\b(?:rev(?:iew)?|cert(?:iorari)?|reh(?:ea)?r?(?:in)?g|appeal|jurisdiction)\.?"
                       r"(?:\s+(?:was|were|has|had|been|later|subsequently|then|also)){0,3}\s+"
                       r"(?:denied|granted|dismissed|declined|accepted)|\baff(?:irme)?'?d|\bapproved|\bquashed|"
                       r"\bdisapproved|\brev'?d|\breversed|\bvacated|\bmodified)(?:\s+(?:in part|on other grounds))?"
                       r"\s*(?:by)?\s*,?\s*$", re.I)


def is_subsequent_history(cite, answer):
    """True for 'review denied, 476 So. 2d 674 (Fla. 1985)'-style history cites (dispositions, not
    authorities the model is relying on)."""
    offs = char_offsets(answer, cite)
    if not offs:
        return False
    return bool(SUBSEQ_RE.search(answer[max(0, offs[0] - 60):offs[0]]))


def parenthetical(cite, answer):
    """-> (court_text, year) from the '(Fla. 2022)' after the cite (or the California-style '(2021)'
    just before it), or (None, None)."""
    offs = char_offsets(answer, cite)
    if not offs:
        return None, None
    before = re.search(r"\(([^()]*?)\s?(\d{4})\)\s*$", answer[max(0, offs[0] - 40):offs[0]])
    tail = answer[offs[0] + len(cite.get("raw") or ""):offs[0] + len(cite.get("raw") or "") + 80]
    m = PAREN_RE.match(tail)
    if not m:
        if before:
            return (before.group(1).strip() or None), int(before.group(2))
        return None, None
    return m.group(1).strip(), int(m.group(2))


def scope_from_court(court_text, q_state):
    if court_text:
        m = re.search(r"(\d+)(?:st|nd|rd|th)\s+Cir\.", court_text)
        if m:
            return {"court": f"ca{m.group(1)}"}
        if "D.C. Cir." in court_text:
            return {"court": "cadc"}
        if "Fed. Cir." in court_text:
            return {"court": "cafc"}
        if re.search(r"\b[NSEWMC]\.?D\.", court_text) or "Bankr." in court_text:
            return {}
        for ab in sorted(STATE_ABBR, key=len, reverse=True):
            if court_text.startswith(ab):
                return {"state": STATE_ABBR[ab]}
    if q_state and q_state != "us":
        return {"state": q_state}
    return {}


# ------------------------------------------------------------------ main entry
def _nrep(r):
    return re.sub(r"[^a-z0-9]", "", (r or "").lower())


def _court_ok(court_text, hit_court):
    """Coarse level check, Florida and federal circuits only (other states' court names vary too much)."""
    if not court_text:
        return True, "no parenthetical court"
    ct, hc = court_text.strip(), hit_court.lower()
    if re.search(r"\d+(?:st|nd|rd|th)\s+Cir\.", ct):
        return ("circuit" in hc), f"'{ct}' vs '{hit_court}'"
    if ct.startswith("Fla."):
        if re.search(r"DCA|Dist\.|App\.", ct):
            return ("district court of appeal" in hc), f"'{ct}' vs '{hit_court}'"
        if re.fullmatch(r"Fla\.", ct):
            return ("supreme court of florida" in hc), f"'{ct}' vs '{hit_court}'"
    return True, "not checked"


def _year(d):
    return int(d[:4]) if d and d[:4].isdigit() else None


def _year_ok(y, band, paren_year):
    if y is None:
        return False, "no year"
    if band and not (band["lo"] <= y <= band["hi"]):
        return False, f"year {y} outside band {band['lo']}-{band['hi']}"
    if paren_year and abs(y - paren_year) > 1:
        return False, f"year {y} vs parenthetical {paren_year}"
    return True, "ok"


def _corroborate(ev, base, name, call_tool):
    """Route 3, always run: other opinions quoting this exact cite next to the claimed party name.
    Accepts on its own when routes 1-2 failed (unless they found the case under a different
    volume/page: miscited_real_case) and, when routes 1-2 already accepted, records
    cite_corroborated_by_courts = N so the audit can see whether volume+page were confirmed too."""
    try:
        d = call_tool("search_cases", {"q": f'"{base}"', "per_page": 10})
        citers = []
        name_tok = [t for side in _split_sides(name or "") if side for t in _toks(side)
                    if len(t) > 2 and t not in GENERIC and t not in HISTORY_WORDS] if name else []
        for c in d.get("results") or []:
            snip = re.sub(r"\s+", " ", c.get("snippet") or "")
            m = re.search(re.escape(base).replace(r"\ ", r"\s*"), snip)
            if not m:
                continue
            window = snip[max(0, m.start() - 120):m.start()].lower()
            if name_tok and any(_tok_in(t, _toks(window)) for t in name_tok):
                citers.append({"cluster_id": c.get("cluster_id"), "case_name": c.get("case_name"),
                               "date_filed": c.get("date_filed"), "snippet": snip[:240]})
        ev["attempts"].append({"route": "cited_by_courts", "n_corroborating": len(citers)})
        ev["cite_corroborated_by_courts"] = len(citers)
        if citers:
            ev["corroborating_citers"] = citers[:3]
            if ev["status"] != "unindexed_real" and not ev.get("miscited_real_case"):
                # a real case found under a DIFFERENT volume/page stays a miscite even if some courts
                # copied the same wrong cite (seen: Riley v. Fatt, 47 So. 2d 769, cited as 42 by 3 courts)
                ev.update(status="unindexed_real", route="cited_by_courts",
                          hit={"route": "cited_by_courts", "cluster_id": None, "citers": citers[:3]})
    except Exception as e:
        ev["attempts"].append({"route": "cited_by_courts", "error": str(e)[:200]})
    return ev


def reconcile(cite, answer, q_state, call_tool):
    """call_tool(name, args) -> parsed JSON dict (or raises). Returns an evidence dict with
    status 'unindexed_real' or 'fabricated'."""
    raw = cite.get("raw") or ""
    base = f"{cite.get('volume')} {cite.get('reporter')} {cite.get('page')}"
    name = claimed_name(cite, answer)
    court_text, paren_year = parenthetical(cite, answer)
    band = year_band(cite.get("reporter"), cite.get("volume"))
    ev = {"raw": raw, "claimed_name": name, "paren": [court_text, paren_year], "year_band": band,
          "attempts": [], "status": "fabricated", "route": None, "hit": None}

    my_rep = _nrep(cite.get("reporter"))
    my_vp = (str(cite.get("volume")), str(cite.get("page")))

    generic_side = bool(name) and any(
        side is not None and not [t for t in _toks(side) if t not in GENERIC] for side in _split_sides(name))

    def consider(route, cand, extra=None):
        cname, cdate = cand.get("case_name") or "", cand.get("date_filed") or ""
        nm = bool(name) and name_match(name, cname)
        yok, why = _year_ok(_year(cdate), band, paren_year)
        if yok and generic_side and paren_year and _year(cdate) != paren_year:
            yok, why = False, f"'State/People/U.S.' party: year {_year(cdate)} must equal parenthetical {paren_year}"
        cok, cwhy = _court_ok(court_text, cand.get("court") or "")
        # the hit's own citations: a different volume/page in the SAME reporter means the model miscited
        same_rep = []
        for ct in cand.get("citations") or []:
            m = re.match(r"^(\d+)\s+(.+?)\s+(\d+)$", ct.strip())
            if m and _nrep(m.group(2)) == my_rep:
                same_rep.append((m.group(1), m.group(3)))
        if same_rep and my_vp not in same_rep:
            pok, pwhy = False, f"hit is cited {cand.get('citations')} - model's volume/page is wrong"
        else:
            pok, pwhy = True, ("hit carries this cite" if same_rep else "hit has no cite in this reporter (unindexed)")
        rec = {"route": route, "cluster_id": cand.get("cluster_id"), "case_name": cname, "date_filed": cdate,
               "court": cand.get("court"), "hit_citations": cand.get("citations"), "name_match": nm,
               "year_check": why, "court_check": cwhy, "cite_check": pwhy}
        if extra:
            rec.update(extra)
        ev["attempts"].append(rec)
        if nm and not pok:
            ev["miscited_real_case"] = rec
        if nm and yok and cok and pok:
            ev.update(status="unindexed_real", route=route, hit=rec)
            return True
        return False

    # route 1: check_citation with expected_case_name
    if name:
        try:
            d = call_tool("check_citation", {"citation": base, "expected_case_name": name})
            cands = list(d.get("matches") or []) + list(d.get("name_candidates") or [])
            nc = (d.get("name_check") or {})
            for key in ("candidates", "name_candidates"):
                cands += list(nc.get(key) or []) if isinstance(nc, dict) else []
            ev["attempts"].append({"route": "check_citation", "found": d.get("found"),
                                   "n_candidates": len(cands), "note": (d.get("note") or "")[:160]})
            for c in cands:
                if consider("check_citation", c):
                    return _corroborate(ev, base, name, call_tool)
        except Exception as e:
            ev["attempts"].append({"route": "check_citation", "error": str(e)[:200]})

    # route 2: search_cases by distinctive party words
    if name:
        words = distinctive_words(name)
        if words:
            scope = scope_from_court(court_text, q_state)
            specific = [w for w in words if " " not in w and w not in GENERIC]   # lhs first, then rhs
            queries = [" ".join(f'"{w}"' for w in words)]
            if specific:
                queries.append(f"name:{specific[0]}")
            combos = [(qq, sc) for qq in queries for sc in ([scope, {}] if scope else [{}])]
            for q, sc in combos:
                args = {"q": q, "per_page": 10}
                args.update(sc)
                if band and band.get("lo") and band.get("hi", 9999) < 9999:
                    args["date_from"] = f"{band['lo']}-01-01"
                    args["date_to"] = f"{band['hi']}-12-31"
                try:
                    d = call_tool("search_cases", args)
                except Exception as e:
                    ev["attempts"].append({"route": "search_cases", "args": args, "error": str(e)[:200]})
                    continue
                res = d.get("results") or []
                ev["attempts"].append({"route": "search_cases", "args": args, "n_results": len(res)})
                for c in res:
                    if consider("search_cases", c, {"query": args}):
                        return _corroborate(ev, base, name, call_tool)

    return _corroborate(ev, base, name, call_tool)


if __name__ == "__main__":
    print(json.dumps(year_band(sys.argv[1], int(sys.argv[2])), indent=1))
