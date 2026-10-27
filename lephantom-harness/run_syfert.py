#!/usr/bin/env python3
# usage: python3 run_syfert.py --split test|subset130|pilot20|train [--limit N] [--concurrency 3] [--tag T] [--raw-dir DIR] [--remap-only] [--mapping v1|v2]
"""Arm 1: Syfert check_brief alone (no LLM). Each excerpt is sent as the brief text to the MCP tool check_brief
(mode=defend). The raw body is kept (results/syfert_raw/<ex_id>.json) and two deterministic mappings turn its
findings into predicted segments (both stored as separate runs: syfert:strict:<tag>, syfert:broad:<tag>):

  strict: cite unresolved with verdict strong / interior_mismatch (fabricated), or a cited_as_fabricated verdict
          -> the cite's raw span; party_check.verdict == mismatch -> the cite's raw span;
          quote_checks[].integrity == absent or verdict == misquote -> the quoted words (located in the excerpt).
  broad:  strict + any unresolved cite (not_indexed / exists_unindexed / unknown) -> cite span;
          quote verdict near / paraphrase -> quote span; page_pin.verdict interior_mismatch / exterior (or a
          quote_check page_pin with inside == false) -> cite span;
          cited_for.cited_for_match == false or verdict proposition_mismatch -> the sentence preceding the cite.
  cited_for (mcp83, third column): strict + cites[].cited_for_check verdict proposition_uncited with confidence hard
          -> the brief's proposition (located in the excerpt). Advice-confidence rows are mapped as cited_for_advice
          (in no column). Neither strict nor broad changes.
Predicted segment text is always a substring of the excerpt where one can be located (the paper's matcher is
substring-based), else the tool's own string. Statute/rule findings are ignored (case citations only)."""
import argparse, concurrent.futures as cf, datetime as dt, json, os, re, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # citebench/ for cb_common
from cb_common import MCPClient, MCPError, load_keys
import lp_common as L

RAW_DIR = os.path.join(L.RESULTS, "syfert_raw")
FAB_VERDICTS = {"strong", "interior_mismatch"}
CITED_FOR_VERDICTS = {"proposition_uncited", "proposition_contradicted", "proposition_entity_mismatch"}   # mcp83 v1 + v2 cited_for column


def ws_norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def locate(text, needle):
    """Return the excerpt's own substring for needle (whitespace/quote-insensitive), or needle itself."""
    if not needle:
        return None
    if needle in text:
        return needle
    # build a whitespace-insensitive regex, tolerant of curly/straight quotes and apostrophes
    parts = [re.escape(w) for w in ws_norm(needle).replace("*", " ").replace("_", " ").split(" ") if w]
    pat = r"[\s*_]+".join(parts)
    pat = pat.replace(r"\'", "['‘’]").replace(r"'", "['‘’]").replace(r'\"', '["“”]')
    m = re.search(pat, text, flags=re.I)
    if m:
        return text[m.start():m.end()]
    # fallback: strip leading bracket alterations / trailing punctuation
    n2 = re.sub(r"^\[[^\]]*\]\s*", "", ws_norm(needle)).strip(" .,;:")
    if n2 and n2 != ws_norm(needle):
        return locate(text, n2)
    return needle


def preceding_sentence(text, cite_raw):
    """The sentence that precedes (and runs up to) the citation: holding text the excerpt attributes to it."""
    i = text.find(cite_raw)
    if i == -1:
        return None
    head = text[:i]
    # back up over the case name / 'See' signal to the end of the previous sentence boundary
    ends = [m.end() for m in re.finditer(r"[.!?][\"”’')\]]*\s+(?=[A-Z\"“(\[])", head)]
    # the proposition sentence is the one before the citation sentence when the cite sentence is just a cite
    start = ends[-1] if ends else 0
    seg = head[start:].strip()
    if len(seg.split()) < 6 and len(ends) >= 2:      # cite sentence carries no proposition: take the previous one
        seg = head[ends[-2]:].strip()
    seg = re.sub(r"\s*(See|see|See,? e\.g\.,|Cf\.|cf\.|Id\.|Accord)\s*$", "", seg).strip()
    return seg or None


def name_segment(c, text):
    """v5: the span of the case name the brief WROTE (party_check.claimed.lhs), searched backwards from the cite."""
    pc = c.get("party_check") or {}
    nm = ((pc.get("claimed") or {}).get("lhs") or "").strip()
    raw = c.get("raw") or ""
    if not nm or not raw:
        return None
    j = text.find(raw)
    hay = text[:j] if j > 0 else text
    k = hay.rfind(nm)
    if k < 0:
        seg = locate(hay, nm)
        return seg if seg and seg in text else None
    return text[k:k + len(nm)]


def quote_segments(c, text):
    out = []
    checks = c.get("quote_checks") or ([c["quote_check"]] if c.get("quote_check") else [])
    for qc in checks:
        bq = qc.get("brief_quote")
        if not bq:
            continue
        verdict, integ = qc.get("verdict"), qc.get("integrity")
        if MAPPING in ("v3", "v4", "v5", "v6", "v6n") and verdict == "misattributed":
            # v3 (2026-10-19, Graham's yes): the words exist verbatim in ANOTHER opinion (quote_origin) — an attribution question,
            # not an altered quotation; broad only. Planted misquotes never come back misattributed (train: 0 of 126).
            out.append(("broad", "quote_misattributed", locate(text, bq)))
        elif integ == "absent" or verdict == "misquote":
            out.append(("strict", "misquote", locate(text, bq)))
        elif MAPPING in ("v2", "v3", "v4", "v5", "v6", "v6n") and verdict == "near" and qc.get("word_diff"):
            out.append(("strict", "quote_near_diff", locate(text, bq)))
        elif verdict in ("near", "paraphrase") or (verdict == "ok" and isinstance(qc.get("percent"), (int, float)) and qc["percent"] < 100):
            # 'ok' at 95% = one or two words differ: exactly the benchmark's injected misquote; broad only
            out.append(("broad", "quote_near", locate(text, bq)))
        pp = qc.get("page_pin") or {}
        if pp.get("inside") is False and pp.get("pinned") is not None:
            out.append(("broad", "pin_quote_elsewhere", locate(text, c.get("raw"))))
    return out


MAPPING = "v1"   # --mapping v2 (mcp81, 2026-10-16): + quote verdict near with word_diff, page_pin pin_mismatch /
                 # interior_mismatch(quote_elsewhere) and quotes_unattached near rows count as STRICT; same rule for every arm


def map_findings(body, text):
    """-> list of (tier, reason, segment). tier strict findings are also part of broad."""
    found = []
    if MAPPING in ("v2", "v3", "v4", "v5", "v6", "v6n"):
        for o in body.get("quotes_unattached") or []:
            if o.get("verdict") == "near" and o.get("brief_quote"):
                found.append(("strict", "unattached_quote_near", locate(text, o["brief_quote"])))
    for c in body.get("cites") or []:
        raw = c.get("raw") or ""
        span = locate(text, raw) if raw else None
        if c.get("status") == "pin_reference":
            continue
        if c.get("cluster_id") is None:
            v = c.get("verdict")
            if v in FAB_VERDICTS or c.get("verdict_evidence") == "cited_as_fabricated":
                found.append(("strict", f"unresolved:{v}", span))
            elif MAPPING in ("v5", "v6", "v6n") and v == "cite_mismatch":
                # v5 (2026-10-19, mcp94): the named case IS indexed, at another page of the volume, and nothing sits at the page
                # written — mcp87's hard verdict; v4 left it broad only because v1's FAB list predates it
                found.append(("strict", "unresolved:cite_mismatch", span))
            else:
                found.append(("broad", f"unresolved:{v or 'unknown'}", span))
            continue
        pc = c.get("party_check") or {}
        if pc.get("verdict") == "mismatch":
            ns = name_segment(c, text) if (MAPPING == "v5" and pc.get("wrong_part") == "name") else None
            if MAPPING in ("v6", "v6n"):
                # v6 (2026-10-20): the gold marks EITHER the written name or the citation of a name/cite mismatch (dataset v1.1
                # README: "Boone v. Vinson, 15 F.3d 1338" / "599 So. 2d 195"). v6 = v5, plus: when the tool does not say the name
                # is the wrong part, report the span from the written name THROUGH the citation when the name sits within 120 chars
                # before it (the exact-substring matcher then contains whichever part the gold marks); otherwise the cite span.
                # v6n = the written name alone whenever it is found (comparison only).
                nm = name_segment(c, text)
                j = text.find(span)
                i = text.rfind(nm, 0, j) if (nm and j > 0) else -1
                if pc.get("wrong_part") == "name" and nm:
                    ns = nm
                elif MAPPING == "v6n":
                    ns = nm or None
                elif nm and i >= 0 and j - (i + len(nm)) <= 120:
                    e = j + len(span)
                    mpar = re.match(r"\s*\([^()]{2,60}\)", text[e:e + 70])   # the gold cite spans carry "(Tex. Ct. App. 1983)"
                    ns = text[i:e + (mpar.end() if mpar else 0)]
                else:
                    ns = None
            if ns:
                # v5: the tool says the NAME is the wrong part (mcp94 sfpart) → the finding is the written name, not the cite
                found.append(("strict", "name_mismatch:name", ns))
            else:
                found.append(("strict", "name_mismatch", span))
        found += quote_segments(c, text)
        pp = c.get("page_pin") or {}
        if MAPPING in ("v2", "v3", "v4", "v5", "v6", "v6n") and (pp.get("verdict") == "pin_mismatch" or (pp.get("verdict") == "interior_mismatch" and pp.get("reason") == "quote_elsewhere")):
            found.append(("strict", f"pin:{pp.get('verdict')}", span))
        elif MAPPING in ("v4", "v5", "v6", "v6n") and (pp.get("proposition_check") or {}).get("verdict") == "proposition_elsewhere":
            # v4 (2026-10-19, mcp92): the pinned page carries none of the proposition's terms and another page carries them —
            # advice in the tool (verdict unchanged), counted as a pin finding here; real-brief false rate 0.74 % (12 genuine found)
            found.append(("strict", "pin:proposition_elsewhere", span))
        elif pp.get("verdict") in ("interior_mismatch", "exterior", "exterior_pin", "outside"):
            found.append(("broad", f"pin:{pp.get('verdict')}", span))
        cf_ = c.get("cited_for") or {}
        if cf_.get("cited_for_match") is False or c.get("verdict") == "proposition_mismatch":
            seg = preceding_sentence(text, raw)
            if seg:
                found.append(("broad", "proposition_mismatch", seg))
        cfc = c.get("cited_for_check") or {}   # mcp83 (2026-10-16): explicit third column, never part of strict / broad
        if cfc.get("verdict") in CITED_FOR_VERDICTS and cfc.get("brief_proposition"):   # mcp83v2 (2026-10-17): + contradicted / entity_mismatch
            found.append(("cited_for" if cfc.get("confidence") == "hard" else "cited_for_advice", cfc["verdict"], locate(text, cfc["brief_proposition"])))
    # dedupe keeping first reason
    seen, out = set(), []
    for tier, reason, seg in found:
        if seg and (tier, seg) not in seen:
            seen.add((tier, seg)); out.append((tier, reason, seg))
    return out


def predictions(mapped, tier):
    # tiers: strict; broad = strict + broad (not the mcp83 columns); cited_for = strict + mcp83 hard proposition_uncited
    segs = [seg for t, _, seg in mapped if t == "strict" or (tier == "broad" and t == "broad") or (tier == "cited_for" and t == "cited_for")]
    return list(dict.fromkeys(segs))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", default="pilot20")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--remap-only", action="store_true", help="re-run the mappings from stored raw bodies, no MCP calls")
    ap.add_argument("--raw-dir", help="where raw check_brief bodies go / are read from (default results/syfert_raw)")
    ap.add_argument("--mapping", choices=("v1", "v2", "v3", "v4", "v5", "v6", "v6n"), default="v1", help="finding -> span mapping (v2 = mcp81 fields as strict; v3 = v2 minus misattributed quotes; v4 = v3 + mcp92 proposition_elsewhere pins; v5 = v4 + cite_mismatch strict + name-part findings on the written name; v6 = v5 with every name mismatch reported as the written-name-through-citation span, v6n = as the written name alone)")
    a = ap.parse_args()
    global RAW_DIR, MAPPING
    MAPPING = a.mapping
    if a.raw_dir:
        RAW_DIR = os.path.abspath(a.raw_dir)
    rows = L.load_split(a.split)[: a.limit or None]
    con = L.open_db()
    os.makedirs(RAW_DIR, exist_ok=True)
    keys = load_keys()
    run_ids = {t: f"syfert:{t}:{a.split}:{a.tag}" for t in ("strict", "broad", "cited_for")}   # cited_for: mcp83 column
    cfg = json.dumps({"tool": "check_brief", "mode": "defend", "split": a.split, "mapping": a.mapping, "raw_dir": RAW_DIR, "mapping_doc": __doc__[:2000]})
    for t, rid in run_ids.items():
        con.execute("INSERT OR IGNORE INTO runs VALUES(?,?,?,?,?,?)", (rid, f"syfert_{t}", "check_brief", a.split,
                                                                     dt.datetime.now().isoformat(timespec="seconds"), cfg))
    con.commit()
    done = done_strict = L.done_ids(con, run_ids["strict"]) if not a.remap_only else set()
    todo = [r for r in rows if r["id"] not in done]
    print(f"{a.split}: {len(rows)} examples, {len(todo)} to do ({'remap' if a.remap_only else 'MCP'})", flush=True)
    tls = threading.local()
    lock = threading.Lock()

    def work(r):
        t0 = time.time()
        raw_path = os.path.join(RAW_DIR, f"{r['id']}.json")
        err = None
        body = None
        if a.remap_only or (os.path.exists(raw_path) and not a.remap_only and False):
            body = json.load(open(raw_path))
        else:
            try:
                if not hasattr(tls, "mcp"):
                    tls.mcp = MCPClient(keys.get("SYFERT_MCP_TOKEN"), timeout=300)
                txt, is_err, structured = tls.mcp.call_tool("check_brief", {"text": r["text"]})
                if is_err:
                    raise MCPError(f"isError: {txt[:300]}")
                body = structured or json.loads(txt)
                json.dump(body, open(raw_path, "w"), ensure_ascii=False)
            except Exception as e:
                err = f"{type(e).__name__}: {e}"[:500]
        mapped = map_findings(body, r["text"]) if body else []
        lat = round(time.time() - t0, 2)
        ts = dt.datetime.now().isoformat(timespec="seconds")
        with lock:
            for t, rid in run_ids.items():
                preds = predictions(mapped, t)
                con.execute("INSERT OR REPLACE INTO preds VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (rid, r["id"], json.dumps(preds, ensure_ascii=False),
                             json.dumps({"stats": (body or {}).get("stats"), "findings": mapped}, ensure_ascii=False),
                             "deterministic" if body else None, json.dumps([{"name": "check_brief", "latency_s": lat}]),
                             1, 0, 0, 0, 0, 0.0, lat, err, ts))
            con.commit()
        return r["id"], err, len(mapped), lat

    n = 0
    with cf.ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        for ex_id, err, nm, lat in ex.map(work, todo):
            n += 1
            print(f"[{n}/{len(todo)}] {ex_id} findings={nm} {lat}s {err or ''}", flush=True)
    print("done", run_ids)


if __name__ == "__main__":
    main()
