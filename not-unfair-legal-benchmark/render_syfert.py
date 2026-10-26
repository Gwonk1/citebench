# The renderer of the raw Syfert MCP arm: saved tool body -> answer text. It is the arm's only "intelligence".
# It reads the item's class and the tool's fields, never gold or evidence. The last line is always
# "ANSWER: ..." built only from tool fields (plus the fixed verdict words below).
#
#   find_court     ANSWER: the tool's `bluebook` field of the court it resolved (court_structure.unit_id, else the first row),
#                  else its citation_string (servers before 1.8.0 have no bluebook field).
#   get_treatment  red    -> "<overruled_by.verb> by <overruled_by.case_name>" (else "overruled" + flag_reason)
#                  yellow -> "questioned"; green -> "good law, not overruled"; procedural -> "procedural: <flag_reason>"
#                  + "unpublished" / the tool's status when precedential_status is not Published; the bluebook field leads.
#   check_brief    first correction -> its suggested / replace_with / cite_as, else its problem text;
#                  an unresolved cite -> its verdict ("does not exist" for interior_mismatch / strong / fabricated);
#                  a resolved cite, no corrections -> cite_as or "<case_name>, <cite> (<court_label> <year>)", correct as written;
#                  statutes / rules -> canonical citation + verified, or "not found in the <corpus> corpus" when verified=false.
#   check_citation (fallback when check_brief extracted nothing) -> bluebook / citation + verdict, same verdict words.
import json

FAKE_VERDICTS = ("interior_mismatch", "strong", "fabricated", "likely_fabricated", "hallucinated", "not_found_strong")
PUBLISHED = ("published", "precedential", "")


def brief_has_cites(js):
    if not isinstance(js, dict):
        return False
    st = js.get("statutes") or {}
    return bool(js.get("cites") or (isinstance(st, dict) and st.get("findings")))


def _year(d):
    return (d or "")[:4]


def _built_cite(c):
    """Bluebook-shaped string from a check_brief cites[] row's own fields."""
    if c.get("cite_as"):
        return c["cite_as"]
    case = c.get("case") or {}
    name = case.get("case_name") or ""
    cite = c.get("raw") or " ".join(x for x in (c.get("volume"), c.get("reporter"), c.get("page")) if x)
    paren = " ".join(x for x in (case.get("court_label") or "", _year(case.get("date_filed"))) if x)
    out = (name + ", " if name else "") + cite
    return out + (f" ({paren})" if paren else "")


def _cite_lines(c):
    case = c.get("case") or {}
    tr = c.get("treatment") or {}
    lines = [f"cite {c.get('raw')}: status {c.get('status') or ('resolved' if c.get('cluster_id') else 'unresolved')}"
             + (f", verdict {c.get('verdict')}" if c.get("verdict") else "")]
    if case:
        lines.append(f"  case: {case.get('case_name')} | court {case.get('court_label') or case.get('court') or case.get('court_id')}"
                     f" | decided {case.get('date_filed')} | docket {case.get('docket_number')} | cluster {c.get('cluster_id')}")
    if tr.get("flag_color"):
        lines.append(f"  treatment: {tr.get('flag_color')}" + (f" ({tr.get('top_neg_label')})" if tr.get("top_neg_label") else ""))
    if c.get("overruled_by"):
        lines.append("  overruled_by: " + json.dumps(c["overruled_by"])[:300])
    pc = c.get("party_check") or {}
    if pc.get("verdict") and pc.get("verdict") not in ("match", "no_claim"):
        lines.append(f"  party_check: {pc.get('verdict')} (resolved name {pc.get('resolved_name')})")
    for cand in (c.get("name_candidates") or [])[:3]:
        lines.append("  name_candidate: " + json.dumps(cand)[:300])
    return lines


def _verdict_answer(verdict, raw):
    v = (verdict or "").lower()
    if v in FAKE_VERDICTS:
        return f"does not exist ({raw}: verdict {verdict})"
    if v == "exists_unindexed":
        return f"{raw} (real case, not in the reporter index: verdict exists_unindexed)"
    return f"{raw} (unresolved: verdict {verdict or 'none'})"


def _correction_answer(corr):
    for k in ("suggested", "replace_with", "cite_as", "corrected", "corrected_citation", "case_name"):
        if corr.get(k):
            return str(corr[k])
    if corr.get("verdict") in FAKE_VERDICTS:
        return _verdict_answer(corr.get("verdict"), corr.get("raw"))
    return str(corr.get("problem") or corr.get("note") or corr.get("kind") or "correction without a replacement")


def _statute_answer(f):
    cit = f.get("citation") or f.get("canonical") or ""
    if f.get("verified"):
        return f"{cit} (verified: {f.get('title') or f.get('jurisdiction') or ''})".replace(" ()", "")
    return f"{cit}: not found in the {f.get('jurisdiction') or 'statute'} corpus (verified=false)"


def render_brief(js):
    lines = []
    cites = js.get("cites") or []
    corrections = js.get("corrections") or []
    st = js.get("statutes") or {}
    findings = st.get("findings") or [] if isinstance(st, dict) else []
    lines.append("check_brief stats: " + json.dumps(js.get("stats") or {}))
    # warnings and per-cite notes are generic tool prose: left in the saved body, not echoed into the answer.
    for c in cites:
        lines.extend(_cite_lines(c))
    for corr in corrections:
        lines.append(f"correction ({corr.get('kind') or corr.get('verdict')}): {str(corr.get('problem') or '')[:400]}")
    for f in findings:
        lines.append("statute: " + _statute_answer(f))
    if corrections:
        ans = _correction_answer(corrections[0])
    elif cites:
        c = cites[0]
        if c.get("cluster_id") and (c.get("status") in (None, "resolved")):
            ans = _built_cite(c) + ", correct as written"
        elif c.get("status") == "pin_reference" and c.get("cite_as"):
            ans = c["cite_as"]
        else:
            ans = _verdict_answer(c.get("verdict"), c.get("raw"))
    elif findings:
        ans = _statute_answer(findings[0])
    else:
        ans = None
    return lines, ans


def render_citation(js):
    lines = ["check_citation: " + json.dumps({k: js.get(k) for k in ("status", "verdict", "type", "verified", "citation") if k in js})]
    if js.get("type") in ("statute", "rule", "regulation") or "verified" in js and not js.get("case"):
        return lines, _statute_answer(js)
    case = js.get("case") or {}
    if js.get("bluebook"):
        lines.append("bluebook: " + js["bluebook"])
    if case:
        lines.append(f"case: {case.get('case_name')} | court {case.get('court_label') or case.get('court_id')} | decided {case.get('date_filed')} | docket {case.get('docket_number')}")
    for cand in (js.get("name_candidates") or [])[:3]:
        lines.append("name_candidate: " + json.dumps(cand)[:300])
    v = js.get("verdict")
    if v and v not in ("ok", "match", "verified", "found"):
        return lines, _verdict_answer(v, js.get("citation") or "")
    if js.get("bluebook"):
        return lines, js["bluebook"] + ", correct as written"
    if case.get("case_name"):
        return lines, case["case_name"] + ", correct as written"
    return lines, None


def render_court(js):
    courts = js.get("courts") or []
    want = (js.get("court_structure") or {}).get("unit_id")
    pick = next((c for c in courts if want and c.get("id") == want), courts[0] if courts else None)
    # Only the picked row is echoed: the grader reads "right" over the whole answer, and other rows'
    # citation strings would hand out passes the tool did not give.
    lines = [f"find_court query {js.get('query')!r}: {len(courts)} courts"]
    if not pick:
        return lines, None
    lines.append(f"picked {pick.get('id')} ({'court_structure' if want and pick.get('id') == want else 'first row'}): "
                 f"{pick.get('full_name')} | bluebook {pick.get('bluebook')!r} | citation_string {pick.get('citation_string')!r}")
    return lines, (pick.get("bluebook") or pick.get("citation_string") or "").strip() or None


def render_treatment(js):
    tr = js.get("treatment") or {}
    flag = (tr.get("flag") or "").lower()
    ob = js.get("overruled_by") or {}
    lines = [f"get_treatment: {js.get('bluebook') or js.get('case_name')} | flag {flag} | precedential_status {js.get('precedential_status')}"]
    if tr.get("flag_reason"):
        lines.append("flag_reason: " + tr["flag_reason"])
    if js.get("ambiguous_citation"):
        lines.append("ambiguous_citation: " + json.dumps(js.get("candidates"))[:400])
    if flag == "red":
        if ob.get("case_name"):
            verdict = f"{ob.get('verb') or 'overruled'} by {ob['case_name']}" + (f" ({ob['year']})" if ob.get("year") else "")
        else:
            verdict = "overruled" + (f" ({tr['flag_reason']})" if tr.get("flag_reason") else "")
    elif flag == "yellow":
        verdict = "questioned"
    elif flag == "green":
        verdict = "good law, not overruled"
    elif flag == "procedural":
        verdict = "procedural" + (f": {tr['flag_reason']}" if tr.get("flag_reason") else "")
    else:
        verdict = f"no treatment flag ({flag or 'none'})"
    status = (js.get("precedential_status") or "").strip()
    if status.lower() not in PUBLISHED:
        verdict += f"; {status.lower()}" if status.lower() == "unpublished" else f"; {status} (precedential_status)"
    head = js.get("bluebook") or ""
    return lines, (head + " — " if head else "") + verdict


def render(row, body):
    calls = body.get("calls") or []
    out = []
    ans = None
    for c in calls:
        out.append(f"[{c.get('tool')} {json.dumps(c.get('args'))[:200]}]")
        js = c.get("json")
        if c.get("is_error") or not isinstance(js, dict):
            out.append("tool error: " + (c.get("text") or "")[:300])
            continue
        if c["tool"] == "find_court":
            lines, a = render_court(js)
        elif c["tool"] == "get_treatment":
            lines, a = render_treatment(js)
        elif c["tool"] == "check_brief":
            lines, a = render_brief(js)
        elif c["tool"] == "check_citation":
            lines, a = render_citation(js)
        else:
            lines, a = [], None
        out.extend(lines)
        if a:
            ans = a  # the fallback call, when there is one, answers
    out.append("ANSWER: " + (ans or "no answer from the tool"))
    return "\n".join(out)
