#!/usr/bin/env python3
# usage: PYTHONDONTWRITEBYTECODE=1 python3 audit/build_packet.py [--out PATH] [--frozen PACKET]   (from ~/projects/citebench)
#   no --frozen : draw a NEW sample (50 quotes + 10 name mismatches) from the current results.db
#   --frozen P  : keep the sample in packet P (same ids, quotes, verdicts, frame) and only rebuild the
#                 attribution / passages / answer sentences from the current results.db rows
"""Build audit/packet.json: 50 quote verdicts (35 absent + 15 found) + 10 name-mismatch verdicts,
stratified by model in proportion to each paid run's total n_cites, seed 20260922.
Reads results.db read-only (?mode=ro). Opinion text via Syfert MCP get_case (token from keys.env).

Quote attribution (fixed 2026-09-22 after the Q11 / Q35 misattributions):
  * rows graded g5+ carry _citebench.quote_results[] (verdict, kind, cluster_id/case_name = the case the quote
    was FOUND in, or for an absent quote the CLOSEST case with paraphrase_ratio, plus `searched`). The card's
    "found in" / "closest" comes from there and nowhere else.
  * rows graded before g5 have no per-quote record: the card says so and falls back to the attribution the
    ANSWER makes, resolved from its text: a cite right after the quote (full cite, "Id.", short form
    "Commerce, 695 So. 2d at 385", "Name, supra") resolved to its full citation, else the closest preceding
    citation reference in the answer. check_brief's quote pairing is never used for attribution.
  * every card also carries the answer's own sentence(s) holding the quote and the cite, verbatim."""
import argparse, bisect, json, os, random, re, sqlite3, sys, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True
from cb_common import MCPClient, load_keys          # noqa: E402
from grade import norm_words                         # noqa: E402
from reconcile import char_offsets                   # noqa: E402

SEED = 20260922
N_ABSENT, N_FOUND, N_NAME = 35, 15, 10
OUT = os.path.join(ROOT, "audit", "packet.json")

# ---------------------------------------------------------------------------------------------------------
# opinion text + passage search

_mcp = None
case_cache = {}


def get_case(cid):
    global _mcp
    if not cid:
        return {}
    cid = int(cid)
    if cid in case_cache:
        return case_cache[cid]
    if _mcp is None:
        _mcp = MCPClient(load_keys()["SYFERT_MCP_TOKEN"])
    parts, offset, meta = [], 0, {}
    for _ in range(4):
        raw, err, _ = _mcp.call_tool("get_case", {"cluster_id": cid, "include_text": True,
                                                  "max_chars": 150000, "offset": offset})
        if err:
            break
        j = json.loads(raw)
        if not meta:
            meta = {k: j.get(k) for k in ("cluster_id", "case_name", "bluebook", "url", "court", "date_filed")}
        ot = j.get("opinion_text") or {}
        parts.append(ot.get("text") or "")
        if str(ot.get("truncated")).lower() != "true" or not ot.get("next_offset"):
            break
        offset = int(ot["next_offset"])
    meta["text"] = "".join(parts)
    case_cache[cid] = meta
    return meta


TOK = re.compile(r"[a-z0-9]+")


def tokens(text):
    t = text.lower().replace("’", "'").replace("‘", "'")
    return [(m.group(0), m.start(), m.end()) for m in TOK.finditer(t)]


def best_run(quote, text):
    """Longest contiguous run of the quote's words in the opinion text -> (run_len, char_start, char_end)."""
    q = norm_words(quote)
    tt = tokens(text)
    words = [w for w, _, _ in tt]
    pos = {}
    for i, w in enumerate(words):
        pos.setdefault(w, []).append(i)
    best = (0, None, None, None)
    for qi in range(len(q)):
        if len(q) - qi <= best[0]:
            break
        for p in pos.get(q[qi], ()):
            if qi and p and words[p - 1] == q[qi - 1]:
                continue            # not a maximal start
            k = 0
            while qi + k < len(q) and p + k < len(words) and words[p + k] == q[qi + k]:
                k += 1
            if k > best[0]:
                best = (k, tt[p][1], tt[p + k - 1][2], qi)
    return best, len(q)


def passage(quote, cid, searched_ids):
    """Longest word-for-word run of the quote in ONE case's opinion, 300 chars either side (None: no text)."""
    m = get_case(cid)
    t = m.get("text") or ""
    if not t:
        return None
    (k, s, e, _), qlen = best_run(quote, t)
    a, b = (max(0, s - 300), min(len(t), e + 300)) if s is not None else (0, 0)
    return {"cluster_id": int(cid), "case_name": m.get("case_name"), "bluebook": m.get("bluebook"),
            "url": m.get("url"), "grader_searched": int(cid) in searched_ids, "run_words": k, "quote_words": qlen,
            "pct": round(100 * k / qlen, 1) if qlen else 0,
            "before": t[a:s] if s is not None and k >= 3 else "", "match": t[s:e] if s is not None and k >= 3 else "",
            "after": t[e:b] if s is not None and k >= 3 else ""}


def norm_s(s):
    return " ".join(norm_words(s or ""))


def case_ref(cid, name=None):
    m = get_case(cid) if cid else {}
    return {"cluster_id": int(cid) if cid else None, "case_name": m.get("case_name") or name,
            "bluebook": m.get("bluebook"), "url": m.get("url")}


# ---------------------------------------------------------------------------------------------------------
# attribution the ANSWER makes: citation references in the text, Id. / short form / supra resolved

ID_RE = re.compile(r"(?<![A-Za-z])(?:[Ii]d|[Ii]bid)\.(?:,?\s+at\s+\*?\d+(?:\s*[-–—]\s*\d+)?(?:\s*(?:n|&)\.?\s*\d+)?)?")
SHORT_RE = re.compile(r"\b(\d{1,4})\s+([A-Z][A-Za-z.'’]*(?:\s+(?:[A-Z][A-Za-z.'’]*|\d[a-z]{1,2}))*)\s+at\s+\*?\d+"
                      r"(?:\s*[-–—]\s*\d+)?")
SUPRA_RE = re.compile(r"\bsupra\b(?:,?\s+at\s+\*?\d+)?")
SIGNALS = {"see", "cf", "also", "accord", "but", "compare", "contra", "the", "in", "e.g", "and", "with", "v", "vs"}
NONCASE_RE = re.compile(r"§|\bFed\.\s*R\.|\bRule\s+\d|\bAm\.\s*Jur\.|\bRestatement\b|\bCorbin\b|\bWilliston\b|"
                        r"\bU\.S\.C\.|\bC\.F\.R\.|\bStat\.\s")
ABBR = {"v", "vs", "co", "corp", "inc", "ltd", "no", "nos", "so", "ct", "app", "supp", "dist", "cir", "fla", "cal",
        "st", "ave", "dept", "mr", "mrs", "ms", "dr", "jr", "sr", "bros", "assn", "ass'n", "p'ship", "cty", "cnty",
        "comm'n", "rev", "ann", "stat", "civ", "crim", "proc", "evid", "r", "p", "u.s", "s", "f", "e.g", "i.e",
        "cf", "ed", "id", "ibid", "al", "etc", "misc", "div", "mun", "gen", "gov't", "int'l", "nat'l", "sup",
        "super", "jud", "ch", "pa", "ga", "tex", "ill", "mich", "mass", "conn", "wis", "minn", "tenn", "ky",
        "va", "md", "ohio", "ariz", "colo", "nev", "okla", "ore", "wash", "ala", "miss", "ark", "la", "neb", "kan",
        "del", "vt", "me", "am", "jur", "op", "ord", "n.y", "n.j", "n.c", "s.c", "n.d", "s.d", "d.c", "w.va", "n.h", "r.i", "n.m", "dca"}


def _norm_rep(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def sentence_bounds(text):
    """Sentence start offsets: a break after . ! ? (plus closing quotes/brackets) + whitespace + a capital or
    opening quote, unless the word before the period is an abbreviation / single letter; and at every newline."""
    starts = [0]
    for m in re.finditer(r"([.!?])([\"”’')\]]*)(\s+)(?=[A-Z\"“(\[*])", text):
        if m.group(1) == ".":
            w = re.search(r"([A-Za-z.'’]+)$", text[max(0, m.start() - 12):m.start()])
            w = (w.group(1) if w else "").lower().replace("’", "'").strip(".")
            if not m.group(2) and (w in ABBR or len(w) == 1):
                continue
        starts.append(m.end())
    for m in re.finditer(r"\n+", text):
        starts.append(m.end())
    return sorted(set(starts))


def _sent_start(starts, pos):
    return starts[bisect.bisect_right(starts, pos) - 1]


def _sent_end(starts, pos, text):
    i = bisect.bisect_right(starts, pos)
    end = starts[i] if i < len(starts) else len(text)
    return len(text[:end].rstrip())


def _cite_name(c):
    return ((c.get("case") or {}).get("case_name") or "", ((c.get("claimed") or {}).get("lhs") or ""),
            ((c.get("party_check") or {}).get("claimed") or {}).get("lhs") or "")


def citation_refs(text, body):
    """Every citation reference in the answer, in order, each resolved to a check_brief cite dict (or None):
    kind full | id | short | supra | noncase."""
    cites = body.get("cites") or []
    refs = []
    for c in cites:
        raw = c.get("raw") or ""
        for off in char_offsets(text, c):
            # the case name in front of a full cite belongs to it
            refs.append({"kind": "full", "start": off, "end": off + len(raw), "cite": c})
    covered = [(r["start"], r["end"]) for r in refs]

    def inside(a, b):
        return any(x <= a < y or x < b <= y for x, y in covered)

    for m in SHORT_RE.finditer(text):
        if inside(m.start(), m.end()):
            continue
        vol, rep = m.group(1), _norm_rep(m.group(2))
        refs.append({"kind": "short", "start": m.start(), "end": m.end(), "vol": vol, "rep": rep})
    for m in ID_RE.finditer(text):
        if not inside(m.start(), m.end()):
            refs.append({"kind": "id", "start": m.start(), "end": m.end()})
    for m in SUPRA_RE.finditer(text):
        pre = text[max(0, m.start() - 60):m.start()]
        pre = re.split(r"[.;:!?(]\s|\n", pre)[-1]            # this citation clause only
        words = [w for w in re.finditer(r"[A-Z][A-Za-z'’&-]+", pre) if w.group(0).lower() not in SIGNALS]
        if words and not inside(m.start(), m.end()):
            st = m.start() - len(pre) + words[0].start()
            refs.append({"kind": "supra", "start": st, "end": m.end(),
                         "words": [w.group(0).lower() for w in words]})
    for m in NONCASE_RE.finditer(text):
        if not inside(m.start(), m.end()):
            refs.append({"kind": "noncase", "start": m.start(), "end": m.end()})
    # a case named in running text ("the very next sentence in Mejia (at 1177) notes: ...") by its key party word
    keys = {}
    for c in cites:
        k = party_key(c)
        if k:
            keys.setdefault(k, []).append(c)
    for k in keys:
        for m in re.finditer(r"(?<![A-Za-z])" + re.escape(k) + r"(?![A-Za-z])", text, flags=re.I):
            if m.group(0)[:1].isupper():
                refs.append({"kind": "name", "start": m.start(), "end": m.end(), "key": k})
    refs.sort(key=lambda r: (r["start"], r["kind"] != "full"))
    last_case, fulls = None, []
    for r in refs:
        r["text"] = text[r["start"]:r["end"]]
        if r["kind"] == "full":
            r["resolved"], r["via"] = r["cite"], "full citation"
            fulls.append(r)
        elif r["kind"] == "short":
            hit = next((f for f in reversed(fulls) if str(f["cite"].get("volume")) == r["vol"]
                        and _norm_rep(f["cite"].get("reporter")) == r["rep"]), None)
            r["resolved"] = hit["cite"] if hit else None
            r["via"] = f"short form '{r['text']}' -> {hit['cite'].get('raw')}" if hit else f"short form '{r['text']}' (no matching full cite)"
        elif r["kind"] == "supra":
            hit = next((f for f in reversed(fulls) if any(
                w in (" ".join(_cite_name(f["cite"])) + " " + text[max(0, f["start"] - 120):f["start"]]).lower()
                for w in r["words"])), None)
            r["resolved"] = hit["cite"] if hit else None
            r["via"] = f"'{r['text']}' -> {hit['cite'].get('raw')}" if hit else f"'{r['text']}' (no matching full cite)"
        elif r["kind"] == "id":
            r["resolved"] = last_case["resolved"] if last_case else None
            r["via"] = (f"'{r['text']}' -> antecedent {last_case['text']}" if last_case
                        else f"'{r['text']}' with no earlier case citation")
            # Bluebook Id. refers to the immediately preceding authority; a secondary source / rule mentioned
            # in between is flagged rather than followed (the benchmark attributes quotes to cases)
            if last_case and any(x["kind"] == "noncase" and last_case["start"] < x["start"] < r["start"] for x in refs):
                r["note"] = "a non-case authority (statute, rule, treatise) is mentioned between the case cite and this Id."
        elif r["kind"] == "name":
            continue
        else:
            r["resolved"], r["via"] = None, "non-case authority"
        if r["kind"] in ("full", "short", "supra") and r["resolved"] is not None:
            last_case = r
        elif r["kind"] == "id" and r["resolved"] is not None:
            last_case = {**last_case, "start": r["start"]}
    for r in refs:
        if r["kind"] == "name":
            full = [f for f in fulls if f["cite"] in keys[r["key"]]]
            prev = [f for f in full if f["start"] <= r["start"]]
            hit = prev[-1] if prev else (full[0] if full else None)
            r["resolved"] = hit["cite"] if hit else None
            r["via"] = f"case named in the text ('{r['text']}') -> {hit['cite'].get('raw')}" if hit else "case name"
    return refs


GENERIC_PARTY = {"state", "states", "people", "united", "commonwealth", "city", "county", "department", "dept",
                 "estate", "matter", "parte", "the", "commissioner", "comm", "board", "town", "village", "district",
                 "school", "florida", "government", "secretary", "director", "company", "corporation", "insurance",
                 "bank", "national", "american", "first", "general", "court", "inc", "corp", "division", "office",
                 "unknown", "john", "doe", "roe", "jane", "fla", "rel"}


def party_key(c):
    """First distinctive party word of the name the answer gave (claimed lhs, then rhs), else the corpus name."""
    cl = c.get("claimed") or (c.get("party_check") or {}).get("claimed") or {}
    for side in (cl.get("lhs"), cl.get("rhs"), *(((c.get("case") or {}).get("case_name") or "").split(" v. ", 1))):
        for w in re.findall(r"[A-Z][A-Za-z'’-]{3,}", side or ""):
            if w.lower() not in GENERIC_PARTY:
                return w
    return None


PAREN_GAP_RE = re.compile(r"[\s,;\d–—\-n.&]*(?:\([^()\n]{0,80}\)[\s,]*){0,2}\(\s*(?:[a-z][a-z ,]{0,40}?\s*:?\s*)?[\"“‘']?\s*")
SENT_BREAK_RE = re.compile(r"[.!?][\"”’')\]]*\s+(?=[A-Z\"“])")


CONNECT = {"v.", "vs.", "of", "the", "and", "&", "ex", "rel.", "in", "re", "for", "de", "la", "on", "to", "by", "a",
           "an", "at", "e.g.,", "see", "see,", "also", "cf.", "accord", "but", "compare"}


def _abbr_before(text, i):
    """True when the period at text[i] ends an abbreviation (v., Co., So.) or an initial, not a sentence."""
    if text[i] != ".":
        return False
    w = re.search(r"([A-Za-z.'’]+)$", text[max(0, i - 12):i])
    w = (w.group(1) if w else "").lower().replace("’", "'").strip(".")
    return w in ABBR or len(w) == 1


def _is_case_name_lead(tail):
    """'Commerce P'ship v. Equity Contracting Co., ' / 'See Tipper, ' : a case name (with an optional signal)
    directly in front of the cite, not a new sentence of prose ('The Court cited Mobil Oil v. Shevin, ')."""
    if not re.search(r",\s*$", tail):
        return False
    for w in tail.split():
        if not (w[:1].isupper() or w[:1].isdigit() or w.lower() in CONNECT or not w[:1].isalpha()):
            return False
    return True


def find_quote(text, quote):
    i = text.find(quote)
    if i >= 0:
        return i, i + len(quote)
    # tolerate quote-mark / whitespace differences
    pat = r"\s+".join(re.escape(w) for w in quote.split())
    m = re.search(pat, text)
    return (m.start(), m.end()) if m else (-1, -1)


def model_attribution(text, body, quote):
    """-> dict: the case the ANSWER attributes the quote to, how it was resolved, and the verbatim answer
    sentence(s) carrying the quote and that cite (with offsets of both inside it)."""
    qs, qe = find_quote(text, quote)
    if qs < 0:
        return {"via": "quote not located in the answer text", "cite": None}
    starts = sentence_bounds(text)
    refs = [r for r in citation_refs(text, body) if r["kind"] != "noncase" and not (qs <= r["start"] < qe)]
    para_start = text.rfind("\n\n", 0, qs)
    para_start = 0 if para_start < 0 else para_start
    para_end = text.find("\n\n", qe)
    para_end = len(text) if para_end < 0 else para_end
    chosen, how = None, None
    # 1) a citation reference right after the quote: same line, and the only sentence break between them is
    #    the one ending the quoted sentence ('..." Id. at 385.' / '...." Commerce v. Equity, 695 So. 2d ...')
    notes = []
    # 0) the quote sits in the explanatory parenthetical of the citation right before it:
    #    'Nousari v. Nousari, 94 So. 3d 704, 707 (Fla. 4th DCA 2012) ("The purpose ...")'
    cref = [r for r in refs if r["kind"] != "name"]
    prev = [r for r in cref if r["end"] <= qs]
    if prev and PAREN_GAP_RE.fullmatch(text[prev[-1]["end"]:qs]):
        chosen, how = prev[-1], "quote is in the parenthetical of the citation before it"
    for r in ([] if chosen else cref):
        if r["start"] < qe:
            continue
        gap = text[qe:r["start"]]
        if "\n" in gap or len(gap) > 250:
            break
        # sentence breaks from the quote's own closing punctuation up to the reference
        breaks = [m for m in SENT_BREAK_RE.finditer(text, max(0, qe - 1)) if m.start() < r["start"]
                  and not _abbr_before(text, m.start())]
        tail = text[breaks[-1].end():r["start"]] if breaks else gap
        if len(breaks) == 0 or (len(breaks) == 1 and (not tail.strip() or _is_case_name_lead(tail))):
            if re.search(r"\b(?:citing|quoting)\b", gap, re.I):
                # '"..." — citing Commonwealth v. Johnson': the quoted opinion cites that case; the answer
                # attributes the words to the authority before the quote
                notes.append(f"the cite after the quote is introduced by '{re.search(r'(?i)citing|quoting', gap).group(0)}' "
                             f"({r['text']}), so it is not taken as the quote's source")
            else:
                chosen, how = r, "citation right after the quote"
        break
    # 2) else the closest preceding reference: same paragraph first, then anywhere earlier in the answer
    if chosen is None:
        before = [r for r in refs if r["end"] <= qs]
        if before:
            chosen = before[-1]
            how = ("closest preceding citation in the same paragraph" if chosen["start"] >= para_start
                   else "closest preceding citation earlier in the answer")
    if chosen is None:
        after = [r for r in cref if r["start"] >= qe]
        if after:
            chosen, how = after[0], "no citation before the quote; first citation after it"
    out = {"how": how, "cite": None, "ref_text": None, "via": None, "note": None}
    if chosen is None:
        out["how"] = "no citation in the answer"
    else:
        if chosen.get("note"):
            notes.append(chosen["note"])
        out.update(cite=chosen.get("resolved"), ref_text=chosen["text"], via=chosen["via"],
                   note="; ".join(notes) or None)
    # the answer sentence(s): from the start of the sentence holding the quote (or the cite, if earlier in the
    # same paragraph) to the end of the sentence holding the cite (or the quote)
    lo, hi = _sent_start(starts, qs), _sent_end(starts, qe, text)
    cite_sentence = None
    if chosen is not None:
        if chosen["start"] >= qe:
            hi = max(hi, _sent_end(starts, chosen["end"] - 1, text))
        elif chosen["start"] >= para_start and qs - chosen["start"] <= 900:
            lo = min(lo, _sent_start(starts, chosen["start"]))
        else:
            a, b = _sent_start(starts, chosen["start"]), _sent_end(starts, chosen["end"] - 1, text)
            cite_sentence = {"text": text[a:b], "ref": [chosen["start"] - a, chosen["end"] - a]}
    out["answer_sentence"] = text[lo:hi]
    out["marks"] = {"quote": [qs - lo, qe - lo]}
    if chosen is not None and cite_sentence is None:
        out["marks"]["ref"] = [chosen["start"] - lo, chosen["end"] - lo]
    out["cite_sentence"] = cite_sentence
    return out


# ---------------------------------------------------------------------------------------------------------
# the grader's record for one quote

def grader_searched_pre_g5(meta, body, gv):
    """Which opinions a pre-g5 grader searched (it did not record them per quote)."""
    searched = list(meta.get("verified_clusters") or [])
    if gv and gv.startswith("g4"):          # g4: every resolved cited case, name verdict or not
        searched += list(meta.get("mismatch_clusters") or [])
    for ev in meta.get("reconciliation") or []:
        hid = (ev.get("hit") or {}).get("cluster_id")
        if ev.get("status") == "unindexed_real" and hid:
            searched.append(hid)
    for c in body.get("cites") or []:
        if c.get("resolution") == "name_year" and c.get("cluster_id"):
            searched.append(c["cluster_id"])
    return [int(x) for x in dict.fromkeys(searched)]


def find_quote_result(meta, quote):
    qr = meta.get("quote_results")
    if not qr:
        return None
    nq = norm_s(quote)
    return (next((r for r in qr if r.get("quote") == quote), None)
            or next((r for r in qr if norm_s(r.get("quote")) == nq), None))


def build_quote_item(item_id, kind, r, qid, quote, gv, body, model, qi=None, frozen=None):
    meta = body.get("_citebench") or {}
    sent = meta.get("sent_text") or ""
    qr = find_quote_result(meta, quote)
    notes = []
    if qr is not None:
        searched = [int(s[0]) for s in qr.get("searched") or [] if s and s[0]]
        searched_names = {int(s[0]): s[1] for s in qr.get("searched") or [] if s and s[0]}
        verdict = qr.get("verdict")
        found_in = case_ref(qr.get("found_in") or qr.get("cluster_id"), qr.get("case_name")) \
            if verdict == "found" and (qr.get("found_in") or qr.get("cluster_id")) else None
        closest_id = qr.get("closest") or (qr.get("cluster_id") if verdict != "found" else None)
        closest = case_ref(closest_id, qr.get("case_name")) if closest_id else None
        if closest is not None:
            closest["ratio"] = qr.get("ratio", qr.get("paraphrase_ratio"))
        attr = {"source": "grader", "grader_version": gv, "verdict": verdict, "kind": qr.get("kind"),
                "found_in": found_in, "closest": closest,
                "searched": [case_ref(c, searched_names.get(c)) for c in searched]}
        if frozen and verdict != frozen:
            notes.append(f"This item was sampled as '{frozen}'; the row has since been regraded ({gv}) and the "
                         f"grader now says '{verdict}'. The card shows the verdict being audited.")
    else:
        searched = grader_searched_pre_g5(meta, body, gv)
        attr = {"source": "answer_text", "grader_version": gv, "verdict": frozen or kind, "kind": None,
                "found_in": None, "closest": None, "searched": [case_ref(c) for c in searched]}
        if meta.get("quote_results") is not None or (gv or "") >= "g5":
            why = next((s[1] for s in meta.get("quote_spans_skipped") or [] if norm_s(s[0]) == norm_s(quote)), None)
            notes.append(f"The current grade ({gv}) no longer checks this passage"
                         + (f": {why}." if why else " (not among its extracted quotes)."))
        else:
            notes.append(f"Graded {gv or 'before versioning'}, before per-quote records (g5): the grader did not "
                         "record which case it searched this quote in. The case shown is the one the answer "
                         "attributes it to (cite after the quote, Id., short form or supra resolved to the full "
                         "citation; else the closest preceding citation).")
    ma = model_attribution(sent, body, quote)
    mc = ma.get("cite") or {}
    mcid = mc.get("cluster_id")
    mcase = case_ref(mcid, (mc.get("case") or {}).get("case_name")) if mcid else \
        {"cluster_id": None, "case_name": None, "bluebook": None, "url": None}
    cited = {**mcase, "raw": mc.get("raw"), "ref_text": ma.get("ref_text"), "attributed_by": ma.get("how"),
             "via": ma.get("via"), "note": ma.get("note"), "grader_searched": bool(mcid and int(mcid) in searched),
             "excluded_as_name_mismatch": bool(mcid and mcid in (meta.get("mismatch_clusters") or [])),
             "unresolved": bool(mc) and not mcid}
    # the passage shown: from the case the grader found it in / came closest in; pre-g5, from the answer's case
    pid = ((attr["found_in"] or {}).get("cluster_id") or (attr["closest"] or {}).get("cluster_id")
           or (mcid if attr["source"] == "answer_text" else None))
    shown = passage(quote, pid, set(searched)) if pid else None
    # the longest run in any searched case, when it beats the shown one (context for the auditor)
    elsewhere = None
    for cid in searched:
        if cid == pid:
            continue
        p = passage(quote, cid, set(searched))
        if p and p["run_words"] >= 3 and p["run_words"] > (shown or {}).get("run_words", 0) and \
                (elsewhere is None or p["run_words"] > elsewhere["run_words"]):
            elsewhere = p
    qc_hit = None
    nq = norm_s(quote)
    for c in body.get("cites") or []:
        for qc in list(c.get("quote_checks") or []) + ([c["quote_check"]] if c.get("quote_check") else []):
            bq = norm_s(qc.get("brief_quote"))
            if bq and (bq == nq or bq in nq or nq in bq):
                qc_hit = dict(qc, cluster_id=c.get("cluster_id"), case_name=(c.get("case") or {}).get("case_name"))
                break
        if qc_hit:
            break
    qpos = sent.find(quote)
    return {
        "id": item_id, "section": "quote", "stratum": kind,
        "run_id": r, "model": model, "qid": qid, "quote_index": qi,
        "quote": quote,
        "context": sent[max(0, qpos - 250): qpos + len(quote) + 120] if qpos >= 0 else None,
        "grader_verdict": frozen or ("absent" if kind == "absent" else "found"),
        "grader_rule": "absent = no contiguous run of >= 80% of the words of every ellipsis segment appears in any verified case the answer cites",
        "attribution": attr,
        "attribution_notes": notes,
        "answer_sentence": ma.get("answer_sentence"),
        "answer_marks": ma.get("marks"),
        "cite_sentence": ma.get("cite_sentence"),
        "cited_case": cited,
        "check_brief": ({k: qc_hit.get(k) for k in ("verdict", "source", "integrity", "percent", "best_match",
                                                     "cluster_id", "case_name")} if qc_hit else None),
        "cases_searched": [{"cluster_id": cid, "case_name": get_case(cid).get("case_name"),
                            "text_chars": len(get_case(cid).get("text") or "")} for cid in searched],
        "passage": shown if shown and shown["run_words"] >= 3 else None,
        "passage_case": case_ref(pid) if pid else None,
        "longer_run_elsewhere": elsewhere,
    }


# ---------------------------------------------------------------------------------------------------------

def load_rows(con):
    return con.execute(
        "SELECT g.run_id, g.qid, g.n_cites, g.n_quote_absent, g.n_name_mismatch, g.grader_version, g.check_brief_json, "
        "a.raw_answer FROM grades g JOIN answers a ON a.run_id=g.run_id AND a.qid=g.qid "
        "WHERE g.run_id NOT LIKE 'mock%' AND g.run_id NOT LIKE 'local%' ORDER BY g.run_id, g.qid").fetchall()


def allocate(total, pools, cites_by_run):
    """Largest-remainder allocation proportional to run cite counts, capped by pool size."""
    alloc = {r: 0 for r in cites_by_run}
    left = total
    active = {r for r in cites_by_run if pools.get(r)}
    while left > 0 and active:
        w = sum(cites_by_run[r] for r in active)
        quota = {r: left * cites_by_run[r] / w for r in active}
        base = {r: min(int(quota[r]), len(pools[r]) - alloc[r]) for r in active}
        for r in active:
            alloc[r] += base[r]
        left -= sum(base.values())
        order = sorted(active, key=lambda r: -(quota[r] - int(quota[r])))
        for r in order:
            if left and alloc[r] < len(pools[r]):
                alloc[r] += 1
                left -= 1
        active = {r for r in active if alloc[r] < len(pools[r])}
    return alloc


def name_item(item_id, r, qid, cid, body, model):
    grp = [c for c in body.get("cites") or [] if c.get("cluster_id") == cid]
    m = get_case(cid)
    sent = body["_citebench"].get("sent_text") or ""
    off = min((o for c in grp for o in char_offsets(sent, c)), default=None)
    return {
        "id": item_id, "section": "name", "stratum": "name_mismatch",
        "run_id": r, "model": model, "qid": qid,
        "cites": [{"raw": c.get("raw"), "claimed": c.get("claimed") or (c.get("party_check") or {}).get("claimed"),
                   "verdict": (c.get("party_check") or {}).get("verdict"),
                   "resolved_name": (c.get("party_check") or {}).get("resolved_name")} for c in grp],
        "resolved_case": {k: m.get(k) for k in ("case_name", "bluebook", "cluster_id", "url", "court", "date_filed")},
        "context": sent[max(0, off - 250): off + 200] if off is not None else None,
        "grader_verdict": "name_mismatch",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT, help="where to write the packet (default audit/packet.json)")
    ap.add_argument("--frozen", help="keep the sample of this packet; rebuild attribution only")
    args = ap.parse_args()

    con = sqlite3.connect(f"file:{os.path.join(ROOT, 'results', 'results.db')}?mode=ro", uri=True)
    runs = {r[0]: r[1] for r in con.execute("SELECT run_id, model FROM runs")}
    rows = load_rows(con)
    snapshot_ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    bodies, gvs = {}, {}
    for run_id, qid, n_cites, nqa, nnm, gv, cbj, raw in rows:
        try:
            bodies[(run_id, qid)] = json.loads(cbj)
            gvs[(run_id, qid)] = gv
        except (TypeError, ValueError):
            continue

    if args.frozen:
        old = json.load(open(args.frozen))
        items = []
        for it in old["items"]:
            key = (it["run_id"], it["qid"])
            if key not in bodies:
                print("row missing from results.db, item kept as is:", it["id"], key, file=sys.stderr)
                items.append(it)
                continue
            if it["section"] == "quote":
                items.append(build_quote_item(it["id"], it["stratum"], it["run_id"], it["qid"], it["quote"],
                                              gvs[key], bodies[key], runs.get(it["run_id"]),
                                              qi=it.get("quote_index"), frozen=it["grader_verdict"]))
            else:
                items.append(name_item(it["id"], it["run_id"], it["qid"], it["resolved_case"]["cluster_id"],
                                       bodies[key], runs.get(it["run_id"])))
        packet = {k: v for k, v in old.items() if k != "items"}
        packet["attribution_rebuilt"] = snapshot_ts
        packet["attribution_grader_versions"] = sorted({gvs.get((i["run_id"], i["qid"])) or "none" for i in items})
        packet["items"] = items
    else:
        cites_by_run, pool_abs, pool_found, pool_name, grader_versions = {}, {}, {}, {}, set()
        for run_id, qid, n_cites, nqa, nnm, gv, cbj, raw in rows:
            cites_by_run[run_id] = cites_by_run.get(run_id, 0) + (n_cites or 0)
            grader_versions.add(gv)
            body = bodies.get((run_id, qid))
            if body is None:
                continue
            meta = body.get("_citebench") or {}
            absent_left = list(meta.get("quotes_absent") or [])
            for i, qt in enumerate(meta.get("quotes_extracted") or []):
                if qt in absent_left:
                    absent_left.remove(qt)
                    pool_abs.setdefault(run_id, []).append((run_id, qid, i))
                else:
                    pool_found.setdefault(run_id, []).append((run_id, qid, i))
            for cid in sorted(set(meta.get("mismatch_clusters") or [])):
                pool_name.setdefault(run_id, []).append((run_id, qid, cid))
        rng = random.Random(SEED)
        samples = {}
        for name, total, pools in (("absent", N_ABSENT, pool_abs), ("found", N_FOUND, pool_found),
                                   ("name", N_NAME, pool_name)):
            alloc = allocate(total, pools, cites_by_run)
            picks = []
            for r in sorted(alloc):
                if alloc[r]:
                    picks += [(r, x) for x in rng.sample(sorted(pools[r]), alloc[r])]
            samples[name] = (alloc, picks)
        items = []
        for kind in ("absent", "found"):
            for run_id, (r, qid, qi) in samples[kind][1]:
                body = bodies[(r, qid)]
                quote = body["_citebench"]["quotes_extracted"][qi]
                items.append(build_quote_item(f"Q{len(items) + 1:02d}", kind, r, qid, quote, gvs[(r, qid)], body,
                                              runs.get(r), qi=qi))
        for run_id, (r, qid, cid) in samples["name"][1]:
            n = len([i for i in items if i["section"] == "name"]) + 1
            items.append(name_item(f"N{n:02d}", r, qid, cid, bodies[(r, qid)], runs.get(r)))
        packet = {
            "built": snapshot_ts, "seed": SEED, "grader_versions": sorted(v for v in grader_versions if v),
            "source": "results/results.db (read-only snapshot; runs still being written at build time)",
            "frame": {"cites_by_run": cites_by_run,
                      "absent_quotes_by_run": {r: len(v) for r, v in pool_abs.items()},
                      "found_quotes_by_run": {r: len(v) for r, v in pool_found.items()},
                      "name_mismatch_clusters_by_run": {r: len(v) for r, v in pool_name.items()}},
            "allocation": {k: {r: n for r, n in v[0].items() if n} for k, v in samples.items()},
            "items": items,
        }
    json.dump(packet, open(args.out, "w"), indent=1, ensure_ascii=False)
    print("wrote", args.out)
    print(json.dumps({k: packet.get(k) for k in ("frame", "allocation")}, indent=1)[:2000])
    qitems = [i for i in items if i["section"] == "quote"]
    print("items", len(items), "no-passage", sum(1 for i in qitems if not i.get("passage")),
          "grader-attributed", sum(1 for i in qitems if (i.get("attribution") or {}).get("source") == "grader"),
          "text-attributed", sum(1 for i in qitems if (i.get("attribution") or {}).get("source") == "answer_text"))


if __name__ == "__main__":
    main()
