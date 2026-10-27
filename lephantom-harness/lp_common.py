# usage: imported by run_syfert.py / run_llm.py / score.py (not run directly)
"""LePhantomCite harness: data, prompts, prediction parsing, the paper's matching rule, results DB.

Scoring (paper §4.1 + repo hallucination_checker_evaluator.py, re-implemented here; nothing is imported from the
untrusted dump): strings are stripped + lower-cased; p matches g when p in g or g in p (either-direction substring),
plus the repo's ellipsis rule ('...' / '…' splits a span into fragments that must appear in order in the other
string). Micro-averaged over examples: TP_pred = predictions matching >= 1 gold span; recall numerator = gold spans
matched by >= 1 prediction (the repo counts the two sides separately; so do we).
'optional' gold spans (paper App. 8.4): a prediction matching one counts as a true positive, missing one is not a
false negative. The repo's evaluate_entry default treats them as ordinary gold; score.py reports that variant too."""
import json
import os
import re
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RESULTS = os.path.join(HERE, "results")
DB_PATH = os.path.join(RESULTS, "lephantom.db")
TYPES = ["non_existent_citation", "case_name_mismatch", "wrong_pincite", "misquote", "content_misrepresentation"]


# ---------------------------------------------------------------- data
def load_split(split):
    path = os.path.join(DATA, "test.jsonl" if split in ("test", "subset130") else "train.jsonl")
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    if split == "subset130":
        keep = set(open(os.path.join(DATA, "subset130.txt")).read().split())
        rows = [r for r in rows if r["id"] in keep]
    elif split == "train130":   # dev subset for prompt / harness A/Bs (2026-10-19); never the test split
        keep = set(open(os.path.join(DATA, "train130.txt")).read().split())
        rows = [r for r in rows if r["id"] in keep]
    elif split == "pilot20":
        keep = set(open(os.path.join(DATA, "pilot20.txt")).read().split())
        rows = [r for r in rows if r["id"] in keep]
    elif split not in ("test", "train", "train130"):
        raise SystemExit(f"unknown split {split}")
    return rows


# ---------------------------------------------------------------- prompts (paper repo, max_steps=0 path)
ENV_DESC = """
You are expected to extract all CASE CITATIONS (no other types of citations like regulations, statutes, or other legal sources) and to:
1) Verify Citation Existence: Determine whether the reporter citations correspond to real, verifiable legal cases.
2) Verify Citation Consistency: Determine whether the case names before the reporter citations and the reporter citations themselves refer to the same legal case.
3) Verify Quotation: Determine whether the quoted language appears verbatim in the cited opinion.
4) Verify Pincite: Determine whether the pincite (page number) accurately reflects the location of the quoted language or proposition within the cited opinion.
5) Verify Contextual Accuracy: Assess whether the quoted language or proposition is presented in a manner consistent with its original context within the cited opinions.

BRIEF TEXT: {brief}

"""

NONAGENTIC_SYSTEM = ("You are a legal expert tasked with verifying case citations, quotes and holdings in briefs. "
                     "Provide your best prediction based on the task description.\n\n## Environment\n{env}")

# get_response_requirements() with the two max_steps==0 substitutions boed.py applies
RESPONSE_REQUIREMENTS = (
    "Provide a **list** of hallucinated citations, case names,quotes, and holdings.\n\n"
    "**Format:** A JSON array of only the hallucinated segments, e.g. `[\"string1\", \"string2\"]`.\n\n"
    "**Completeness (required):** Your list must include **every** citation, quote, or holding that you determine to be "
    "hallucinated based on the task description. Do not omit any segment you believe is hallucinated — the response is "
    "evaluated against the full set. Your response must contain exactly those segments (or the citation alone when "
    "sub-items are implied).\n\n"
    "**Important**: If a citation itself is hallucinated, it is assumed that all the quotes and holdings within that "
    "citation are hallucinated as well so there is no need to return them separately. If no hallucinations are found, "
    "return an empty list: `[]`.\n\n"
    "**No reasoning in the final answer:** The `response` field must contain **only** the list —- no reasoning, "
    "explanation, or prose. "
    # The paper's text continues "Put all reasoning, analysis, and explanation in the `reasoning` field, not in `response`."
    # That sentence trips Claude Opus 5.5's reasoning_extraction safeguard (every call refused, 2026-10-16), and the
    # max_steps=0 schema has no reasoning field anyway, so it is dropped for ALL arms here (documented in README).
    "Only return the hallucinated segments: If a holding is hallucinated, return the FULL sentence of the holding.")

NONAGENTIC_USER = ("## Response Requirements\n{req}\n\n## Task\nBased on the task description, provide your best prediction.\n\n"
                   "```json\n{{\n  \"action\": {{\n    \"action_type\": \"PROVIDE_FINAL_RESPONSE\",\n"
                   "    \"response\": \"<ONLY your prediction in the format specified in Response Requirements>\"\n  }},\n"
                   "  \"confidence\": <float between 0.0 and 1.0 representing your confidence in this prediction>\n}}\n```")

# Domain knowledge block from the paper's agent prompt (Appendix 12.2 / prompts/environments/legal_hallucination_checker.py)
DOMAIN_KNOWLEDGE = """### Domain knowledge: legal case citations
- **Citation format**: Typical format is Case Name, Volume Reporter Page (e.g., 557 F.2d 170). The part after the comma is the reporter citation; "at" introduces a pincite (specific page).
- **Quotation format**: ONLY words, phrases, and sentences that are inside quotation marks are considered direct quotes. The presence of ellipses (...) or bracketed ellipses ([...]) only permits omission of intervening text; bracketed alterations like [W]here would not appear verbatim in the opinion and should be omitted from string-match searches. Return the entire sentence as hallucinated if any visible portion of the quotation does not appear verbatim in the opinion.
- **Holding format**: The holding the citation supports usually IMMEDIATELY PRECEDES the citation.
- **Verification hierarchy**: If a citation is already determined to be hallucinated (e.g., case does not exist or case name does not match), treat all quotes and holdings under that citation as hallucinated. In this case, ONLY return the citations that are hallucinated, no need to return the quotes and holdings.
- A wrong pincite alone is sufficient to make the segment hallucinated, even if the case name and the quoted words are otherwise correct. When a tool cannot check the pincite, do not report a pincite error for that citation."""

# Agentic arm: same task + response requirements, with the paper's domain knowledge and a tool-use policy written for the
# Syfert MCP tools (the paper's tool policy is CourtListener-specific; this is its equivalent for these tools).
AGENTIC_SYSTEM_HEAD = ("You are a legal expert verifying case citations, quotes and holdings in a brief excerpt for hallucinations. "
                  "You have tools backed by a database of U.S. case law. Use them to gather evidence for EVERY case citation "
                  "before you answer; do not rely on memory.\n\n## Environment\n{env}\n\n{domain}\n\n"
                  "### Tool policy\n")
# MCPPROFILE_20261027: the Syfert tool policy is the default; run_llm.py --mcp-profile can replace it (TOOL_POLICY_OVERRIDE)
# with another server's policy text so a different MCP runs through the same harness and prompts.
SYFERT_TOOL_POLICY = (
                  "- check_brief(text=the whole excerpt) first: it extracts and resolves every reporter citation, checks the case "
                  "name the excerpt claims against the real case, checks quoted passages word for word, and checks pinpoint pages. "
                  "An unresolved citation with verdict strong / interior_mismatch is likely fabricated; not_indexed / exists_unindexed "
                  "means the index may simply lack it, so weigh volume_coverage and confirm by name with find_case or search_cases "
                  "before calling it hallucinated.\n"
                  "- check_citation(citation, expected_case_name) for one citation; verify_quote(quote, citation) for one quotation; "
                  "get_case(citation or id) reads the opinion so you can check pincites and whether the opinion supports the "
                  "proposition the excerpt attributes to it; search_cases / find_case resolve a case by name.\n"
                  "- Statutes, regulations and rules are out of scope; only case citations count.\n"
                  "- When you have verified every citation (or exhausted your turns), give the final answer.")
AGENTIC_SYSTEM = AGENTIC_SYSTEM_HEAD + SYFERT_TOOL_POLICY
TOOL_POLICY_OVERRIDE = None   # set by run_llm.py --mcp-profile; None = SYFERT_TOOL_POLICY

AGENTIC_POLICY_V2 = """
### How to read check_brief (v2 policy, 2026-10-19)
Copy every segment you report CHARACTER FOR CHARACTER from the excerpt — keep its curly quotes (“ ” ‘ ’), asterisks, dashes and spacing exactly; never retype or normalise.
Citations (cites[]):
- cluster_id null AND verdict strong / interior_mismatch, or verdict_evidence cited_as_fabricated → the citation does not exist: report the citation as written (its quotes and holdings need not be listed separately).
- verdict cite_mismatch, or party_check.verdict mismatch → the case name does not belong to that citation: report the citation.
- not_indexed / exists_unindexed / likely_misprint / unknown → NOT a finding by itself. Confirm with check_citation(citation, expected_case_name=the excerpt's case name) or find_case / search_cases by name and year. Report only when no such case can be found by name AND reporter; if a case of that name exists at that citation, report nothing.
Quotations (quote_checks[]):
- integrity absent, or verdict misquote / paraphrase → the quoted words are not in the opinion: report the quoted words (exactly as the excerpt prints them inside the marks), unless your own verify_quote finds them verbatim.
- verdict near: report ONLY when word_diff shows a real word substituted, added or dropped. Differences of punctuation, capitalisation, bracketed alterations ([W]here, [its]), ellipses, or a dropped internal citation are not misquotes — do not report them.
- misattributed (the words exist verbatim in another opinion) → not a misquote; do not report.
Pinpoint pages (page_pin): pin_mismatch, or interior_mismatch with reason quote_elsewhere, or exterior / past_last → report the citation. interior_pin / inside_span → no pin finding. A pin the tool could not check is never reported.
Holdings (cited_for_check): verdict contradicted / entity_mismatch with confidence hard → report the sentence that states the holding. Anything at advice confidence is a pointer, not a finding: read the pinned page (get_case with the citation and page) and decide.
Content misrepresentation: report the holding sentence (or parenthetical) ONLY when the opinion's text contradicts it or does not address it. A fair paraphrase, a broader or narrower phrasing of a real holding, or a characterisation you merely find arguable is not a hallucination. Never report from memory of the case.
Segment choice: a bad citation, wrong case name or wrong pin → the citation as printed; a misquote → the quoted words; a wrong holding → the sentence/parenthetical stating it. Report each segment once.
"""

AGENTIC_POLICY_V3_EXTRA = """
New check_brief fields (read them; they save you get_case calls):
- page_pin.proposition_check: verdict proposition_elsewhere means the pinned page contains none of the proposition's distinctive terms while another page (found_at / suggested) contains them; both passages are included. Treat it as a strong pointer: read the two passages and, if the proposition is plainly stated on the other page and not on the pinned one, report the citation as a wrong pin. proposition_on_page means the pin is supported; inconclusive means nothing can be said.
- proposition_support: for each resolved citation, the pinned page's text and the best-matching passage with an overlap score. Compare the excerpt's holding sentence against them. A high overlap (≈ 0.8) with consistent meaning supports the holding; a low overlap alone is NOT a finding — open the case with get_case and read the pinned page before reporting a content misrepresentation.
- When neither field is present for a citation, verify the holding yourself with get_case (citation + page) before deciding.
"""

# MCP98_20261020: v4 = v3 + the context_detector tool (check_brief's cites[].support_check says when it can be called)
AGENTIC_POLICY_V4_EXTRA = AGENTIC_POLICY_V3_EXTRA + """- support_check (cites[]): available = context_detector can lay this citation's opinion out next to the excerpt's sentence. Call context_detector (citation = the cite's volume / reporter / first page or cluster_id, pin, sentence = the excerpt's sentence; up to 12 per call with items) for every cite you rely on whose support_check is available, and judge with its instruction. Report unsupported as content misrepresentation, with the excerpt's sentence (or parenthetical) stating the holding as the segment; report overstated only when the holding's meaning changes; cannot_tell is not a finding.
- Report every hard finding the tool makes, in the tool's words: a quote_checks verdict of misquote or absent IS a misquote finding (segment = the quoted words); page_pin.verdict interior_mismatch or pin_mismatch IS a wrong-pincite finding (segment = the citation with its pin); party_check.verdict mismatch IS a case-name finding (segment = the case name as written through its citation). Do not re-litigate these by reading the case unless the tool itself says it is unsure.
- proposition_check verdict proposition_elsewhere IS a wrong-pincite finding unless the pinned page's passage plainly states the proposition; report it with the citation (including its pin) as the segment.
- Segments must be copied character for character from the excerpt: for a wrong pincite the citation as printed including the pin ("550 U.S. at 557"); for a misquote the words inside the quotation marks; for a case-name mismatch the name as the brief wrote it (and its citation when they are adjacent); for content the one sentence that states the holding, not a paraphrase and not two sentences.
"""

TOOL_NUDGE = ("Do not answer from memory. Call check_citation for each case citation in the excerpt (and verify_quote for each "
              "quotation) first; you will be asked for the final answer afterwards.")

FINAL_INSTRUCTION = ("You have no tool calls left. Based on the evidence gathered, provide your final prediction now in the "
                     "required JSON format.")


def nonagentic_messages(text):
    return (NONAGENTIC_SYSTEM.format(env=ENV_DESC.format(brief=text)),
            NONAGENTIC_USER.format(req=RESPONSE_REQUIREMENTS))


def agentic_messages(text, policy="v1"):
    sysmsg = (AGENTIC_SYSTEM if TOOL_POLICY_OVERRIDE is None else AGENTIC_SYSTEM_HEAD + TOOL_POLICY_OVERRIDE).format(env=ENV_DESC.format(brief=text), domain=DOMAIN_KNOWLEDGE)
    if policy in ("v2", "v3", "v4"):
        sysmsg += "\n" + AGENTIC_POLICY_V2
    if policy == "v3":
        sysmsg += AGENTIC_POLICY_V3_EXTRA
    if policy == "v4":   # MCP98_20261020
        sysmsg += AGENTIC_POLICY_V4_EXTRA
    return (sysmsg,
            NONAGENTIC_USER.format(req=RESPONSE_REQUIREMENTS).replace(
                "Based on the task description, provide your best prediction.",
                "Verify every case citation with the tools, then provide your final prediction."))


# ---------------------------------------------------------------- prediction parsing
def _extract_list(s):
    """First balanced JSON array in s (the repo's _extract_list_from_string, re-implemented)."""
    s = s.strip()
    start = s.find("[")
    while start != -1:
        depth, i, in_str, q, esc = 0, start, False, None, False
        while i < len(s):
            c = s[i]
            if esc:
                esc = False
            elif in_str:
                if c == "\\":
                    esc = True
                elif c == q:
                    in_str = False
            elif c in ('"', "'"):
                in_str, q = True, c
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    try:
                        v = json.loads(s[start:i + 1])
                        if isinstance(v, list):
                            return [str(x).strip() for x in v if x is not None and str(x).strip()]
                    except json.JSONDecodeError:
                        pass
                    break
            i += 1
        start = s.find("[", start + 1)
    return None


def parse_predictions(raw):
    """Model output -> (list of predicted segments, parse_status). Accepts the paper's JSON object (action.response as
    a JSON-array string or a list), a bare JSON array, or an array inside a code fence / prose."""
    if raw is None:
        return [], "none"
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x is not None and str(x).strip()], "list"
    s = str(raw).strip()
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.S).strip()   # local thinking models
    s = re.sub(r"<\|channel>thought\n.*?<channel\|>", "", s, flags=re.S).strip()
    # 1) JSON object with action.response
    for m in re.finditer(r"\{", s):
        try:
            obj, _ = json.JSONDecoder().raw_decode(s[m.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            resp = (obj.get("action") or {}).get("response") if isinstance(obj.get("action"), dict) else obj.get("response")
            if resp is None and "predicted_hallucinations" in obj:
                resp = obj["predicted_hallucinations"]
            if isinstance(resp, list):
                return [str(x).strip() for x in resp if x is not None and str(x).strip()], "object_list"
            if isinstance(resp, str):
                lst = _extract_list(resp)
                if lst is not None:
                    return lst, "object_string"
                return ([] if resp.strip() in ("", "[]") else [resp.strip()]), "object_bare"
        break
    # 2) a bare array anywhere
    lst = _extract_list(s)
    if lst is not None:
        return lst, "array"
    return [], "unparsed"


# ---------------------------------------------------------------- matching (paper rule)
def _norm(s):
    return str(s or "").strip().lower()


def _fragments_in_order(frags, text):
    pos = 0
    for f in frags:
        if not f:
            continue
        i = text.find(f, pos)
        if i == -1:
            return False
        pos = i + len(f)
    return True


def is_match(gold, pred):
    g, p = _norm(gold), _norm(pred)
    if not g or not p:
        return False
    if g in p or p in g:
        return True
    for ell in ("...", "…"):
        if ell in p and _fragments_in_order([x.strip() for x in p.split(ell)], g):
            return True
        if ell in g and _fragments_in_order([x.strip() for x in g.split(ell)], p):
            return True
    return False


_ANCHOR_MAP = {"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-", "*": "", "_": ""}


def _canon_map(text):
    """Canonical form of text (quote chars / dashes folded, markdown emphasis dropped, whitespace collapsed) + index map back."""
    out, idx, prev_space = [], [], False
    for i, c in enumerate(text):
        c2 = _ANCHOR_MAP.get(c, c)
        if c2 == "":
            continue
        if c2.isspace():
            if prev_space:
                continue
            c2, prev_space = " ", True
        else:
            prev_space = False
        out.append(c2); idx.append(i)
    return "".join(out), idx


def anchor_span(pred, text, _cache={}):
    """ANCHOR (2026-10-19, Graham's yes): a predicted segment that is not an exact substring of the excerpt is snapped to the
    excerpt's own characters when it differs ONLY in quote characters (’ ' “ ”), dashes, markdown emphasis (* _) or whitespace.
    The matcher is exact-substring, and Claude writes straight quotes / drops the dataset's asterisks; the finding is the same.
    Nothing else is changed: a segment that cannot be located this way is returned as written."""
    if not pred or pred in text:
        return pred
    key = id(text)
    if key not in _cache or _cache[key][0] is not text:
        _cache.clear(); _cache[key] = (text, _canon_map(text))
    ct, idx = _cache[key][1]
    cp = re.sub(r"\s+", " ", "".join(_ANCHOR_MAP.get(c, c) for c in pred)).strip()
    if not cp:
        return pred
    j = ct.find(cp)
    if j < 0:
        j = ct.lower().find(cp.lower())
        if j < 0:
            return pred
    return text[idx[j]: idx[j + len(cp) - 1] + 1]


def score_example(gold, preds, optional_rule="paper"):
    """gold: {span: type}; preds: list of strings. Returns dict of counts for micro aggregation.
    optional_rule 'paper': optional spans count as TP when matched, never as FN. 'repo': optional spans are ordinary gold."""
    spans = list(dict.fromkeys(k for k in gold if k))
    if optional_rule == "paper":
        req = [s for s in spans if gold[s] != "optional"]
    else:
        req = spans
    preds = list(dict.fromkeys(p for p in preds if p))
    found = sum(1 for g in req if any(is_match(g, p) for p in preds))
    tp = sum(1 for p in preds if any(is_match(g, p) for g in spans))
    by_type = {}
    for g in req:
        t = gold[g] or "untyped"
        d = by_type.setdefault(t, [0, 0])
        d[1] += 1
        if any(is_match(g, p) for p in preds):
            d[0] += 1
    return {"found": found, "gold": len(req), "tp": tp, "pred": len(preds), "by_type": by_type}


def prf(found, gold, tp, pred):
    r = found / gold if gold else 0.0
    p = tp / pred if pred else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


# ---------------------------------------------------------------- results DB
SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, arm TEXT, model TEXT, split TEXT, started_ts TEXT, config_json TEXT);
CREATE TABLE IF NOT EXISTS preds(run_id TEXT, ex_id TEXT, predicted_json TEXT, raw_output TEXT, parse_status TEXT,
  tool_calls_json TEXT, n_turns INTEGER, tokens_in INTEGER, tokens_out INTEGER, cache_read INTEGER, cache_write INTEGER,
  cost_usd REAL, latency_s REAL, error TEXT, ts TEXT, PRIMARY KEY(run_id, ex_id));
CREATE TABLE IF NOT EXISTS calls(run_id TEXT, ex_id TEXT, turn INTEGER, kind TEXT, name TEXT, tokens_in INTEGER,
  tokens_out INTEGER, cache_read INTEGER, cache_write INTEGER, cost_usd REAL, latency_s REAL, ts TEXT);
"""


def open_db(path=DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path, timeout=60, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    return con


def done_ids(con, run_id):
    return {r[0] for r in con.execute("SELECT ex_id FROM preds WHERE run_id=? AND error IS NULL", (run_id,))}
