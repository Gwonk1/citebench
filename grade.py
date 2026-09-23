#!/usr/bin/env python3
# usage: python3 grade.py [--run-id RUN_ID] [--regrade] [--questions FILE] [--concurrency N]
"""Grade every ungraded answer by sending the raw answer text to the Syfert MCP check_brief tool.

Mapping of check_brief output (observed 2026-09-22, server syfert-legal-research 1.1.0) to grades:
  body = {mode, stats{extracted,resolved,unresolved,red,yellow,green,...,party_mismatch?,misquote?,
          truncated_bytes?}, warnings[], cites[], statutes{...}}
  each cite: raw, volume, reporter, page, pin, offsets[], cluster_id (null = not in corpus),
             case{case_name,...}|absent, treatment{flag_color,...}, claimed{lhs,rhs},
             party_check{verdict: match|partial|mismatch, resolved_name}|null,
             quote_checks[{brief_quote,best_match,percent,verdict}], did_you_mean[] (unresolved only)
  Authorities are de-duplicated before counting:
    * resolved cites collapse by cluster_id (a case cited twice, or with a parallel cite, counts once);
    * an UNRESOLVED cite that sits right after a resolved one with only commas/pincites between
      (i.e. a parallel reporter cite such as "..., 94 S. Ct. 1, 5") is not counted as fabricated;
    * g6 PARALLEL CHAINS: reporter cites joined only by commas/semicolons/pincites, up to the year parenthetical
      or the next case name, are ONE authority ("65 N.Y.2d 189, 198, 491 N.Y.S.2d 90, 480 N.E.2d 679 (1985)",
      Michigan "450 Mich 61, 75-76; 537 NW2d 909"). Unresolved members of a chain that has a resolved member are
      parallels; a chain with no resolved member is reconciled once through its first member. A cite whose
      text also occurs inside a chain (check_brief sometimes swallows it as a pincite and reports only a later
      mention) is a parallel of that chain (_citebench.parallel_chain_lead);
    * g6 OFFICIAL STATE REPORTERS: an unresolved official cite ("71 Fla. 177") in the same sentence as a resolved
      regional cite ("71 So. 42") is its parallel; an unpaired one goes through reconciliation and, failing
      that, if its year (parenthetical or volume band) is before 1950, counts as unindexed (route
      old_official_unindexed): the index lacks most old official pagination;
    * g6 SUBSEQUENT HISTORY, resolved or not ("aff'd", "rev'd", "mod", "modified", "cert. denied", "review
      denied", "approved", "quashed", ...), is not an authority: dropped from every count
      (_citebench.subsequent_history_raw);
    * g6 RETRACTED cites: a cite in a self-correction sentence ("I initially checked a wrong page number
      (81 N.Y.2d 612) ...; the correct starting page is 66", "transcription error", "not X but Y", "mis-cited")
      BEFORE the correction marker is dropped (_citebench.retracted_raw); quoted text never triggers this.
  n_cites         = distinct authorities after dedup
  n_fabricated    = unresolved authorities (cluster_id null): the volume/reporter/page does not exist.
                    Includes near misses (right case, wrong page, e.g. "Anderson v. Liberty Lobby, 477 U.S.
                    248" for 242): those have did_you_mean and are listed in _citebench.fabricated_near_miss.
                    Caveat: very recent cases may be corpus coverage gaps.
                    g6: a miscited real case that >= 2 other courts' opinions ALSO cite with the same wrong
                    volume/page stays fabricated (standing policy) but is tagged court_propagated_miscite
                    (_citebench.court_propagated_miscite; report.py column court_propagated).
  n_unindexed     = cites check_brief itself resolved by name + year + court (resolution 'name_year',
                    server-side since 2026-09-22 19:00 UTC) PLUS unresolved authorities that reconcile.py shows are REAL cases the reporter index has
                    not paginated (post-2020 So. 3d, F. App'x, ...): tagged unindexed_real, kept OUT of
                    n_fabricated, still counted in n_cites. Evidence (route, hit cluster/name/date, year band,
                    every attempt) is in _citebench.reconciliation. See reconcile.py for the rules.
                    Strict (unreconciled) fabrication = n_fabricated + n_unindexed.
  n_name_mismatch = resolved authorities whose party_check verdict == 'mismatch' (the cite is real but
                    belongs to a different case: the Mata v. Avianca pattern). 'partial' is NOT counted
                    (usually abbreviation noise) but is tallied in _citebench.n_partial.
                    g4 NAME GUARD: check_brief also says 'mismatch' when the corpus name is dot-less or short
                    ("P.T. v. M.S." vs "Pt v. Ms", "B.J.M." vs "Bjm", "Commerce P'ship 8098 Ltd. P'ship v.
                    Equity Contracting Co." vs "Commerce v. Equity", HRS = Health & Rehabilitative Services).
                    A mismatch is overturned (logged in _citebench.name_guard_overrides) when both parties are
                    equivalent after dot-stripping initials + case-folding, as a token subset either way, or
                    as an acronym, comparing the corpus name against check_brief's claimed parties OR the
                    name the answer itself wrote before the cite.
  n_verified      = resolved authorities that are not name mismatches
  n_quote_absent  = case quotations in the answer found in NONE of the resolved cases the answer cites (verified,
                    name-mismatched or unindexed are all searched; the name verdict and the quote verdict are
                    independent). Every quote's result is in _citebench.quote_results: verdict, kind, the case it
                    was found in (cluster_id, case_name), and the list of cases searched.
                    check_brief's own quote verdicts are kept in the JSON but not used for the count (its pairing
                    breaks on nested/short quotes and it only knows passages other courts re-quoted).
                    EXTRACTION (g5, extract_quotes):
                      - double-quoted passages (straight quotes paired strictly in order per paragraph, plus curly)
                        of >= 6 words; single-quoted spans INSIDE them are part of the outer quote, never separate;
                      - a single-quoted span OUTSIDE any double quote counts only if >= 6 words AND a citation
                        follows it on the same line;
                      - de-duplicated by normalised text;
                      - skipped, with the reason logged in _citebench.quote_spans_skipped:
                        citation signals/parentheticals ("(internal quotation marks omitted)", "quoting ...");
                        spans with a formal rule/statute cite (Fed. R. Civ. P., U.S.C., Fla. Stat., "§ 5") = drafted
                        or rule text, BUT their inner single-quoted passage (outermost pair) is still checked;
                        a citation in quotation marks (< 6 words left once cites are removed);
                        spans inside a quoting/citing parenthetical; title-cased headings/topic names;
                        and any span that is not presented as a case quotation: no citation after it on the same
                        line (within 250 chars), none just before it (60 chars: "..., 94 So. 3d 704 (Fla. 2012)
                        ("..."), and no attribution verb in the 200 chars before it (held, stated, explained,
                        noted, wrote, observed, reasoned, concluded, "as the court put it", ...): the model
                        talking to the user (notes, caveats, suggestions).
                    MATCHING (g5, match_quote): the opinion text is cleaned of star pages ("*277"), bracketed page
                    cues and every digit-only token (footnote markers, page-break numbers) - the quote gets the
                    same digit-drop. Editorial brackets in the quote ([citing], [sic], [emphasis added]) are
                    removed. The quote is split on ellipses; each segment (>= 4 words) must appear in ONE case,
                    either verbatim or as a contiguous run of >= 80% of its words, in the plain text OR in a
                    citation-stripped text (reporter cites with their case names, Id., see-signals and citing/
                    quoting parentheticals removed on both sides), so a quote that omits internal citations
                    ("(citations omitted)" practice) still matches.
                    SUB-CLASSIFICATION (does not change the counts): found -> quote_found_kind 'verbatim' (every
                    segment verbatim) or 'near' (80-99% run); absent -> quote_absent_kind 'paraphrase_in_quotes'
                    (>= 60% of the quote's words appear in order in some window of a cited opinion, difflib
                    matching blocks) or 'fabricated' (< 60%). n_quote_paraphrase feeds report.py paraphrase_share.
  n_red / n_yellow= verified authorities whose treatment.flag_color is red / yellow
  gold_hit        = 1 if a verified authority has cluster_id == gold_cluster_id, or its
                    (volume, reporter, page) equals one parsed from gold_citation
  warned_treatment= 1 if the answer text says a case is bad/weakened law: WARN_RE matches (overruled,
                    abrogated, receded from, disapproved, superseded, questioned, called into question,
                    criticized, limited, no longer good law, negative treatment, red/yellow flag) and the
                    match is not negated earlier in the same sentence clause ("has not been overruled",
                    "no court has questioned", "never receded from" -> not a warning). Text heuristic only;
                    it does not check WHICH case the warning is about. Scored on every answer; the report
                    averages it only over gold_flag yellow/red questions (warned_rate).
  abstained       = 1 if n_cites == 0 AND the answer contains a hedge phrase (ABSTAIN_RE below:
                    "not certain", "cannot verify", "unable to", "I don't know", ...). An answer with no
                    cite and no hedge is neither a hit nor an abstention.
Before auditing, markdown emphasis/heading/blockquote markers are stripped from the answer (observed:
check_brief reports party_check 'no_claim' for "***Hoffman v. Jones***", so un-stripped markdown would hide
name mismatches). The stripped text is what check_brief sees and is stored in _citebench.sent_text.
The full check_brief JSON is stored, plus a "_citebench" key with the dedup decisions, verdict tallies
and stats.truncated_bytes (0 if absent).
"""
import argparse
import concurrent.futures as cf
import json
import re
import threading

from reconcile import char_offsets, claimed_name, is_subsequent_history, reconcile
from cb_common import MCPClient, MCPError, cite_keys, load_gold, load_keys, norm_reporter, open_db

ABSTAIN_RE = re.compile(
    r"not (?:certain|sure|confident|able to (?:verify|confirm|locate|find))|cannot (?:verify|confirm|"
    r"locate|find|identify|provide)|can(?:'|no)t (?:verify|confirm|locate|find|identify)|unable to "
    r"(?:verify|confirm|locate|find|identify)|(?:do|did) not (?:know|have (?:a|access))|don't know|"
    r"could not (?:verify|find|locate|confirm)|uncertain|will not guess|won't guess|rather than guess|"
    r"no (?:verified|reliable) (?:citation|authority)", re.I)
# Bump whenever grading logic (here, reconcile.py or the check_brief contract we rely on) changes, so the
# report can show that every run was graded under the same grader.
GRADER_VERSION = "g6-parallel-20260922"

WARN_RE = re.compile(
    r"\b(?:overruled|overruling|abrogated|abrogation|receded from|recede from|disapproved|superseded|"
    r"questioned|called into (?:question|doubt)|criticized|criticised|limited (?:by|in|to its facts)|"
    r"no longer (?:good|valid|controlling) (?:law|authority)|not good law|bad law|negative(?: subsequent)? "
    r"treatment|(?:red|yellow)[- ]flag(?:ged)?)\b", re.I)
NEGATION_RE = re.compile(r"\b(?:not|never|no|nor|without|neither)\b|n't\b", re.I)
BAD_QUOTE = {"misquote", "absent", "not_found", "no_match"}
PARALLEL_GAP_RE = re.compile(r"^[\s,;\d\-–—n.&]*$")


def strip_md(t):
    """Drop markdown decoration. Every '*' goes except Westlaw star pages ('at *3')."""
    t = re.sub(r"^[ \t]{0,3}(?:#{1,6}[ \t]+|>[ \t]?|[-*+][ \t]+)", "", t or "", flags=re.M)
    t = re.sub(r"\*(?!\d)", "", t)
    t = re.sub(r"(?<![A-Za-z0-9])_{1,3}(?=\S)(.+?)(?<=\S)_{1,3}(?![A-Za-z0-9])", r"\1", t)
    return t.replace("`", "")


CURLY_RE = re.compile("\u201c([^\u201c\u201d]+)\u201d")


def norm_words(t):
    t = t.lower().replace("\u2019", "'").replace("\u2018", "'")
    t = re.sub(r"\[([a-z])\]", r"\1", t)          # [T]he -> the
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.split()


SIGNAL_SPAN_RE = re.compile(r"^\s*\(?\s*(?:quoting|citing|cited in|internal quotation|alterations?|emphas[ie]s|"
                            r"citations? omitted|footnotes? omitted|brackets? in original|see|accord|cf\.)\b", re.I)
# A formal rule/statute cite INSIDE the quote marks ("Fed. R. Civ. P. 12(b)(1)", "42 U.S.C.", "Fla. Stat.",
# "§ 57.105") marks drafted text or rule text, not a quotation of an opinion. A bare mention ("on a Rule
# 12(b)(6) motion") and embedded REPORTER cites (opinions quote other opinions' cites) are kept.
# Trade-off: a genuine opinion passage that itself contains "§ 768.81" is skipped too.
RULE_CITE_RE = re.compile(r"\b(?:Fed\.\s*R\.|R\.\s*(?:Civ|Crim|App|Evid|Jud|Gen|Prac)\.\s*P|Fla\.\s*Stat|U\.S\.C|"
                          r"C\.F\.R|Stat\.\s*(?:Ann\.\s*)?\u00a7)|\u00a7\s*\d", re.I)
PAREN_SIGNAL_RE = re.compile(r"^\s*(?:quoting|citing|internal quotation|alteration|emphasis|citations? omitted)",
                             re.I)


# --- g5 quote engine -----------------------------------------------------------------------------------
# A reporter cite ("242 So.2d 751", "523 U.S. at 89", "241 Mich App 449", "845 So. 2d 927, 929 (Fla. 4th DCA
# 2003)"), optionally preceded by the case name, or an "Id." short cite.
# Written without ambiguous repetition (every token is whitespace-separated, at most 4 of them): the first
# g5 draft used (?:\s?[A-Za-z.]*)* and backtracked exponentially on long capitalised runs in some opinions.
_REPORTER = (r"\b\d{1,4}\s+[A-Z][A-Za-z0-9.']{0,12}(?:\s(?:[A-Z][A-Za-z0-9.']{0,12}|[2-5](?:d|th)))"
             r"{0,4}\s+(?:at\s+)?\d{1,5}\b")
CITE_NEAR_RE = re.compile(_REPORTER + r"|\bId\.|\bid\.\s+at\b|\bIbid\b")
CITE_STRIP_RE = re.compile(
    _REPORTER + r"(?:\s*[,;]\s*\d{1,5}(?:\s*[-\u2013]\s*\d{1,5})?){0,3}(?:\s*n\.\s*\d+)?(?:\s*\([^()]{0,60}\))?"
    r"|\b(?:Id|Ibid)\.(?:\s+at\s+\d+(?:[-\u2013]\d+)?)?"
    r"|\((?:\s*(?:citing|quoting|see|internal|citations?|footnotes?|emphasis|alterations?)\b)[^()]{0,200}\)"
    r"|\b[Ss]ee(?:,?\s+e\.g\.,?|\s+also|\s+generally)?\s+(?=[A-Z])")
_NAME_CONNECT = {"of", "the", "and", "&", "for", "ex", "rel.", "de", "v.", "vs."}
EDITORIAL_RE = re.compile(r"\[(?:citing|quoting|sic|emphasis[^\]]*|internal[^\]]*|citations?[^\]]*|footnotes?[^\]]*|"
                          r"…|\.\s*\.\s*\.)\]", re.I)
STAR_PAGE_RE = re.compile(r"\[?\*{1,2}\s?\d{1,5}\]?|\[\d{1,5}\]")
# Words that present a quoted span as a court's language. Deliberately broad: the g5 audit re-score showed
# that a narrow verb list ("held", "stated") dropped real quotations framed as "the formulation you quoted",
# "the accurate framing is", "the court's statement of the rule:".
ATTRIB_RE = re.compile(r"\b(?:held|holds|holding|explain(?:ed|s)|stat(?:ed|es|ing|ement)|sa(?:id|ys)|not(?:ed|es that)|"
                       r"wr(?:ote|ites)|observ(?:ed|es)|reason(?:ed|s)|conclu(?:ded|des)|emphasi[sz](?:ed|es)|"
                       r"recogni[sz](?:ed|es)|declar(?:ed|es)|announc(?:ed|es)|put it|in the words of|as follows|"
                       r"language|wording|formulation|articulat(?:ed|ion)|phrase|phrasing|framing|quot(?:e|ed|es|ing|ation)|"
                       r"reads|provides|test|standard|rule|opinion|court|justice|judge)\b", re.I)
# The model offering its own approximation, flagged as uncertain: "language close to your phrasing ("...")",
# '"...", but I'm not certain of the exact wording'.
HEDGE_BEFORE_RE = re.compile(r"\b(?:close to|something like|along the lines of|similar to|to the effect)\b[^.]{0,60}$",
                             re.I)
HEDGE_AFTER_RE = re.compile(r"^[^.\n]{0,40}\bnot (?:certain|sure|confident) (?:of|about) the (?:exact )?(?:wording|"
                            r"language|phrasing)", re.I)


def _match_words(t):
    """norm_words minus digit-only tokens: star pages, footnote markers and page-break numbers in opinion text
    ('*277', '56(c),12 its opponent') never break a word run; applied to quote and text alike."""
    return [w for w in norm_words(t) if not w.isdigit()]


def _strip_cites(t):
    """Remove citations: each reporter cite / Id. / citing-parenthetical match, and, for a reporter cite, the
    'Name v. Name,' in front of it (found by walking tokens backwards, no regex backtracking)."""
    t = t or ""
    out, last = [], 0
    for m in CITE_STRIP_RE.finditer(t):
        start = m.start()
        if m.group(0)[:1].isdigit():
            chunk = t[max(last, start - 160):start]
            toks = list(re.finditer(r"\S+", chunk))
            k, seen_v = len(toks), False
            while k > 0:
                w = toks[k - 1].group(0).rstrip(",")
                if w in ("v.", "vs."):
                    seen_v = True
                elif not (w[:1].isupper() or w.lower() in _NAME_CONNECT):
                    break
                k -= 1
            if seen_v and k < len(toks):
                start = max(last, start - 160) + toks[k].start()
        out.append(t[last:start])
        out.append(" ")
        last = m.end()
    out.append(t[last:])
    return "".join(out)


def prep_opinion(raw):
    """-> (plain, cite_stripped) normalised haystacks with star pages / bracketed page cues removed.
    The cite-stripped version lets a quote that omits internal citations ('(citations omitted)' practice)
    match an opinion that has them inline."""
    t = STAR_PAGE_RE.sub(" ", raw or "")
    plain = _match_words(t)
    stripped = _match_words(_strip_cites(t))
    return (" " + " ".join(plain) + " ", " " + " ".join(stripped) + " ", stripped)


def _segments(quote):
    q = EDITORIAL_RE.sub(" ", quote)
    parts = re.split(r"\.\s*\.\s*\.|…|\[\s*\.\.\.\s*\]", q)
    plain = [w for w in (_match_words(x) for x in parts) if len(w) >= 4]
    stripped = [w for w in (_match_words(_strip_cites(x)) for x in parts) if len(w) >= 4]
    return plain, stripped


def segment_found(seg_words, hay, hay_words=None):
    """-> 'verbatim' | 'near' | None. near = a contiguous run of >= 80% of the segment's words."""
    if " " + " ".join(seg_words) + " " in hay:
        return "verbatim"
    need = max(4, int(0.8 * len(seg_words) + 0.999))
    for i in range(0, len(seg_words) - need + 1):
        if " " + " ".join(seg_words[i:i + need]) + " " in hay:
            return "near"
    return None


def _paraphrase_ratio(qwords, hay_words, grams):
    """Best in-order word overlap (difflib matching blocks / quote length) of the quote against any window of
    the opinion that shares a 3-gram with it."""
    import difflib
    L = len(qwords)
    if L < 3:
        return 0.0
    best = 0.0
    cands = set()
    for i in range(L - 2):
        for p in grams.get(tuple(qwords[i:i + 3]), [])[:20]:
            cands.add(max(0, p - i - 5))
    for start in list(cands)[:200]:
        win = hay_words[start:start + L + 15]
        sm = difflib.SequenceMatcher(None, qwords, win, autojunk=False)
        best = max(best, sum(b.size for b in sm.get_matching_blocks()) / L)
    return best


def match_quote(quote, prepared, names):
    """prepared: {cluster_id: (plain, stripped, stripped_words)}. Searches EVERY resolved cited case.
    -> dict(verdict found|absent, kind verbatim|near|paraphrase_in_quotes|fabricated, cluster_id, case_name,
    paraphrase_ratio, searched)."""
    segp, segs = _segments(quote)
    res = {"quote": quote, "searched": [[cid, names.get(cid)] for cid in prepared]}
    if not segp and not segs:
        res.update(verdict="found", kind="verbatim", cluster_id=None, case_name=None, note="no checkable words")
        return res
    best = None
    for cid, (plain, stripped, _) in prepared.items():
        for segl, hay in ((segp, plain), (segs, stripped)):
            if not segl:
                continue
            kinds = [segment_found(w, hay) for w in segl]
            if all(kinds):
                k = "verbatim" if all(x == "verbatim" for x in kinds) else "near"
                if best is None or (k == "verbatim" and best[0] == "near"):
                    best = (k, cid)
    if best:
        res.update(verdict="found", kind=best[0], cluster_id=best[1], case_name=names.get(best[1]))
        return res
    qwords = _match_words(_strip_cites(EDITORIAL_RE.sub(" ", quote)))
    ratio, rcid = 0.0, None
    for cid, (_, _, hw) in prepared.items():
        grams = _GRAMS.get(cid)
        if grams is None:
            grams = {}
            for i in range(len(hw) - 2):
                grams.setdefault((hw[i], hw[i + 1], hw[i + 2]), []).append(i)
            _GRAMS[cid] = grams
        r = _paraphrase_ratio(qwords, hw, grams)
        if r > ratio:
            ratio, rcid = r, cid
    res.update(verdict="absent", kind="paraphrase_in_quotes" if ratio >= 0.6 else "fabricated",
               cluster_id=rcid, case_name=names.get(rcid), paraphrase_ratio=round(ratio, 3))
    return res


_GRAMS = {}
_PREP = {}


def _skip_reason(qt, text, start, end, inner=False):
    """Why a quoted span is not a case quotation (None = it is one)."""
    if SIGNAL_SPAN_RE.match(qt):
        return "citation signal / parenthetical"
    if not inner and RULE_CITE_RE.search(qt):
        return "contains a rule/statute cite (drafted/rule text, not an opinion quotation)"
    if len(_match_words(_strip_cites(EDITORIAL_RE.sub(" ", qt)))) < 6:
        return "citation in quotation marks (fewer than 6 words once the cite is removed)"
    op = text.rfind("(", 0, start)
    if op >= 0 and ")" not in text[op:start] and PAREN_SIGNAL_RE.match(text[op + 1:start]):
        return "inside a quoting/citing parenthetical"
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'’-]*", qt) if len(w) > 3]
    if words and sum(w[0].isupper() for w in words) / len(words) >= 0.8 and not re.search(r"[.;:?!,]\s*$", qt):
        return "title-cased heading/topic name"
    if HEDGE_BEFORE_RE.search(text[max(0, start - 80):start]) or HEDGE_AFTER_RE.search(text[end:end + 120]):
        return "the model's own approximation, flagged as uncertain ('close to', 'not certain of the exact wording')"
    p0 = text.rfind("\n\n", 0, start)
    p1 = text.find("\n\n", end)
    para = text[p0 + 1 if p0 >= 0 else 0:p1 if p1 >= 0 else len(text)]
    if CITE_NEAR_RE.search(para) or ATTRIB_RE.search(text[max(0, start - 250):start]):
        return None
    return "no citation in its paragraph and no attribution in the 250 chars before it: the model talking " \
           "to the user (notes, caveats, suggestions), not quoting a case"


def extract_quotes(text, skipped=None):
    """Case quotations in an answer (g5). Double-quoted passages (straight quotes paired strictly in order per
    paragraph, plus curly quotes) of >= 6 words; single-quoted spans inside them are part of the outer quote.
    Single-quoted spans outside any double quote count only if >= 6 words AND a citation follows. Drafted text
    that is skipped (rule/statute cite inside) still contributes its INNER single-quoted passages. Each span
    must look like a case quotation (_skip_reason); de-duplicated by normalised text. `skipped` collects
    [span, reason] for audit."""
    text = text or ""
    spans, dbl = [], []   # (start, end, quote, kind)
    off = 0
    for para in re.split(r"(\n\s*\n)", text):
        if not para.strip() or re.fullmatch(r"\n\s*\n", para):
            off += len(para)
            continue
        pos = [i for i, ch in enumerate(para) if ch == '"']
        for a, b in zip(pos[0::2], pos[1::2]):
            spans.append((off + a + 1, off + b, para[a + 1:b], "double"))
        for m in CURLY_RE.finditer(para):
            spans.append((off + m.start(1), off + m.end(1), m.group(1), "double"))
        off += len(para)
    dbl = [(a, b) for a, b, _, _ in spans]
    single_re = re.compile(r"(?<![A-Za-z0-9])[‘']([^'‘’\n]{10,400}?)[’'](?![A-Za-z0-9])")
    for m in single_re.finditer(text):
        a, b = m.start(1), m.end(1)
        if not any(x <= a and b <= y for x, y in dbl):
            spans.append((a, b, m.group(1), "single"))
    out, seen = [], set()

    def consider(a, b, qt, kind, inner=False):
        qt = qt.strip()
        if len(_match_words(qt)) < 6:
            return
        if kind == "single":
            after = text[b:b + 250].split("\n", 1)[0]
            if not CITE_NEAR_RE.search(after):
                if skipped is not None:
                    skipped.append([qt, "single-quoted span outside a quotation with no citation after it"])
                return
        why = _skip_reason(qt, text, a, b, inner)
        if why:
            if skipped is not None:
                skipped.append([qt, why])
            if why.startswith("contains a rule/statute cite"):
                # greedy: the outermost '...' pair, so a possessive ("the courts' statutory") inside it
                # does not end the inner quotation early
                for m in re.finditer(r"(?<![A-Za-z0-9])[\u2018'](.{10,400})[\u2019'](?![A-Za-z0-9])", qt):
                    consider(a + m.start(1), a + m.end(1), m.group(1), "inner", inner=True)
            return
        k = " ".join(_match_words(qt))
        if k in seen:
            if skipped is not None:
                skipped.append([qt, "duplicate of an earlier quote"])
            return
        seen.add(k)
        out.append(qt)

    for a, b, qt, kind in sorted(spans):
        consider(a, b, qt, kind)
    return out


NAME_NOISE = {"v", "vs", "versus", "inc", "corp", "corporation", "co", "company", "llc", "ltd", "lp", "llp", "pa",
              "the", "of", "a", "an", "and", "et", "al", "in", "re", "ex", "rel", "for", "on", "to", "at", "by"}


def _name_toks(s):
    """Case-fold; 'P.T.' / 'B.J.M.' -> 'pt' / 'bjm' (the corpus stores initials dot-less: 'Pt v. Ms');
    drop punctuation and noise words."""
    s = (s or "").lower().replace("\u2019", "'").replace("&", " ")
    s = re.sub(r"\b((?:[a-z]\.){2,})", lambda m: m.group(1).replace(".", ""), s)
    s = re.sub(r"'s\b", "", s)
    return [t for t in re.sub(r"[^a-z0-9]+", " ", s).split() if t not in NAME_NOISE]


def _side_equiv(a, b):
    ta, tb = _name_toks(a), _name_toks(b)
    if not ta or not tb:
        return False
    sa, sb = set(ta), set(tb)
    if sa <= sb or sb <= sa:
        return True
    acr_a, acr_b = "".join(t[0] for t in ta), "".join(t[0] for t in tb)
    return (len(acr_a) >= 2 and acr_a in sb) or (len(acr_b) >= 2 and acr_b in sa)   # HRS = Health & Rehab. Servs.


def names_equivalent(claimed, resolved):
    """claimed = 'X v. Y' (or (lhs, rhs)); resolved = corpus name. True when both parties match after
    dot-stripping initials, case-folding, subset (corpus names are often short: 'Commerce v. Equity') or
    acronym comparison, in either order."""
    if isinstance(claimed, str):
        parts = re.split(r"\s+(?:v\.?|vs\.?)\s+", claimed, maxsplit=1)
        if len(parts) != 2:
            return False
        claimed = parts
    rparts = re.split(r"\s+(?:v\.?|vs\.?)\s*", resolved or "", maxsplit=1)
    if len(rparts) != 2 or not all(claimed):
        return False
    (cl, cr), (rl, rr) = claimed, rparts
    return (_side_equiv(cl, rl) and _side_equiv(cr, rr)) or (_side_equiv(cl, rr) and _side_equiv(cr, rl))


def warned(answer):
    for m in WARN_RE.finditer(answer or ""):
        start = max(0, m.start() - 60)
        pre = answer[start:m.start()]
        pre = re.split(r"[.;:!?\n]|\bbut\b|\bhowever\b", pre)[-1]  # same clause only
        if not NEGATION_RE.search(pre):
            return 1
    return 0


# --- g6 citation-structure rules ----------------------------------------------------------------------------
REGIONAL_REPORTERS = re.compile(r"^(?:So\.|N\.\s?E\.|N\.\s?W\.|S\.\s?E\.|S\.\s?W\.|A\.|P\.|NE|NW|SE|SW)\s?(?:\d|$)")
OFFICIAL_STATE_RE = re.compile(r"^(?:Ala|Alaska|Ariz|Ark|Cal|Colo|Conn|Del|Fla|Ga|Haw|Idaho|Ill|Ind|Iowa|Kan|Ky|La|"
                               r"Me|Md|Mass|Mich|Minn|Miss|Mo|Mont|Neb|Nev|N\.\s?H|N\.\s?J|N\.\s?M|N\.\s?Y|NY|"
                               r"N\.\s?C|N\.\s?D|Ohio|Okla|Or|Pa|R\.\s?I|S\.\s?C|S\.\s?D|Tenn|Tex|Utah|Vt|Va|Wash|"
                               r"W\.\s?Va|Wis|Wyo)\b")
# Triggers are about the CITE itself (never generic legal prose such as "should be construed"), and quoted
# text is blanked before searching so an opinion quotation cannot trigger them.
RETRACT_RE = re.compile(r"\b(?:wrong (?:page|cite|citation|volume|number|reporter|pin(?:point)?)|transcription error|"
                        r"typo|I (?:initially|originally|first|earlier|mistakenly) (?:checked|cited|gave|wrote|listed|"
                        r"used|typed|said)|mis-?cited|mistyped|miscopied|"
                        r"(?:cite|citation|page|number|volume|reporter|pin(?:point)?)\s+(?:I gave\s+|above\s+)?"
                        r"(?:was|is)\s+(?:incorrect|wrong|mistaken|erroneous)|"
                        r"not\s+\d{1,4}\s+[A-Z][A-Za-z.\s]{0,12}\d{1,5}\s*,?\s*but\b)", re.I)
KEEP_MARK_RE = re.compile(r"\b(?:correct(?:ed)?|should (?:be|read|have been)|rather|but|actually|instead|right)\b",
                          re.I)
SENT_BOUND_RE = re.compile(r"(?:[a-z]{2,}|\)|\d)[.!?]\s+(?=[A-Z*\u201c\"])|\n")


def _sentence(answer, pos):
    """(start, end) of the sentence containing char position pos."""
    st = 0
    for m in SENT_BOUND_RE.finditer(answer, 0, pos):
        st = m.end()
    m = SENT_BOUND_RE.search(answer, pos)
    return st, (m.start() + 1 if m else len(answer))


def retracted(cite, answer):
    """True when the cite sits in a self-correction sentence ("I initially checked a wrong page number
    (81 N.Y.2d 612) ...; the correct ... is 81 N.Y.2d 66") BEFORE the correction marker: the model withdrew it."""
    for off in char_offsets(answer, cite):
        a, b = _sentence(answer, off)
        sent = re.sub(r'"[^"\n]*"|\u201c[^\u201c\u201d]*\u201d', lambda m: " " * len(m.group(0)), answer[a:b])
        trig = RETRACT_RE.search(sent)
        if not trig:
            continue
        keep = KEEP_MARK_RE.search(sent, trig.start() if not trig.group(0).lower().startswith("not") else trig.end())
        rel = off - a
        if keep is None or rel < keep.start():
            return True
    return False


def is_official_state(c):
    return bool(OFFICIAL_STATE_RE.match(c.get("reporter") or "")) and not REGIONAL_REPORTERS.match(c.get("reporter") or "")


def summarize(answer, body, q, fetch_text=None, reconcile_fn=None):
    cites = body.get("cites") or []
    all_resolved = [c for c in cites if c.get("cluster_id")]
    # check_brief >= 2026-09-22 19:00 UTC resolves index-gap cites server-side by name + year + court
    # (resolution == 'name_year'). They are real but NOT in the reporter index: count them as n_unindexed,
    # not as verified, so fabricated_strict_rate / the index-gap metric keep their meaning.
    name_year = [c for c in all_resolved if c.get("resolution") == "name_year"]
    resolved = [c for c in all_resolved if c.get("resolution") != "name_year"]
    unresolved = [c for c in cites if not c.get("cluster_id")]

    # g6: subsequent history (aff'd / rev'd / mod / cert. denied / review denied ...) and retracted cites are
    # not authorities the answer relies on: drop them from every count, resolved or not.
    history = [c for c in cites if is_subsequent_history(c, answer)]
    retracted_c = [c for c in cites if c not in history and retracted(c, answer)]
    drop = {id(c) for c in history + retracted_c}
    all_resolved = [c for c in all_resolved if id(c) not in drop]
    name_year = [c for c in name_year if id(c) not in drop]
    resolved = [c for c in resolved if id(c) not in drop]
    unresolved = [c for c in unresolved if id(c) not in drop]

    # g6 parallel chains: cites joined only by commas/semicolons/pincites (up to the year parenthetical or the
    # next case name) are ONE authority, e.g. "65 N.Y.2d 189, 198, 491 N.Y.S.2d 90, 480 N.E.2d 679 (1985)".
    # Unresolved members of a chain with a resolved member are parallels; a chain with no resolved member is
    # reconciled once, through its first member.
    pos = []
    for c in all_resolved + unresolved:
        offs = char_offsets(answer, c)
        if offs:
            pos.append((offs[0], offs[0] + len(c.get("raw") or ""), c))
    pos.sort(key=lambda t: t[0])
    chains, cur = [], []
    for st, en, c in pos:
        # st < previous end: check_brief swallowed the next volume as a pincite ("491 N.Y.S.2d 90, 480")
        if cur and (st < cur[-1][1] or (st - cur[-1][1] <= 60 and PARALLEL_GAP_RE.match(answer[cur[-1][1]:st] or ""))):
            cur.append((st, en, c))
        else:
            if cur:
                chains.append(cur)
            cur = [(st, en, c)]
    if cur:
        chains.append(cur)
    parallel, fabricated, lead_of = [], [], {}
    unres_ids = {id(c) for c in unresolved}
    for ch in chains:
        members = [c for _, _, c in ch]
        has_res = any(id(c) not in unres_ids for c in members)
        un = [c for c in members if id(c) in unres_ids]
        if has_res:
            parallel.extend(un)
        elif un:
            fabricated.append(un[0])
            parallel.extend(un[1:])
            for c in un[1:]:
                lead_of[c.get("raw")] = un[0].get("raw")
    # a cite that ALSO occurs inside a chain (check_brief swallowed that occurrence as a pincite and only
    # reported the later mention, e.g. "treat 480 N.E.2d 679 as unverified") is that chain's parallel
    spans_ch = [(ch[0][0], ch[-1][1] + 40, ch[0][2]) for ch in chains if len(ch) > 1 or True]
    keep = []
    for c in fabricated:
        pat = re.escape(f"{c.get('volume')} ") + r"\s*" + re.escape(str(c.get("reporter") or "")).replace(r"\ ", r"\s*") \
            + r"\s+" + re.escape(str(c.get("page")))
        inside = [ (a0, lead) for m in re.finditer(pat, answer) for a0, b0, lead in spans_ch
                   if a0 < m.start() <= b0 and lead is not c ]
        if inside:
            parallel.append(c)
            lead_of[c.get("raw")] = inside[0][1].get("raw")
            continue
        keep.append(c)
    fabricated = keep
    # an official state-reporter cite in the same sentence as a resolved REGIONAL cite = its parallel
    # ("71 So. 42 ... 71 Fla. 177"); the index lacks most old official pagination.
    res_regional = []
    for c in all_resolved:
        if REGIONAL_REPORTERS.match(c.get("reporter") or ""):
            res_regional.extend(char_offsets(answer, c))
    keep = []
    for c in fabricated:
        offs = char_offsets(answer, c)
        if is_official_state(c) and offs:
            a, b = _sentence(answer, offs[0])
            if any(a <= o < b for o in res_regional):
                parallel.append(c)
                continue
        keep.append(c)
    fabricated = keep
    key = lambda c: (c.get("volume"), norm_reporter(c.get("reporter")), c.get("page"))
    by_cluster = {}
    for c in resolved:
        by_cluster.setdefault(c["cluster_id"], []).append(c)

    # reconciliation: unresolved cites that are real cases the reporter index has not paginated
    reconciliation, unindexed, still_fab = [], [], []
    for c in name_year:
        unindexed.append((c, {"status": "unindexed_real", "route": "check_brief_name_year", "raw": c.get("raw"),
                              "hit": {"route": "check_brief_name_year", "cluster_id": c["cluster_id"],
                                      "case_name": (c.get("case") or {}).get("case_name"),
                                      "date_filed": (c.get("case") or {}).get("date_filed"),
                                      "note": c.get("note")}}))
    for c in fabricated:
        ev = reconcile_fn(c) if reconcile_fn else None
        if ev and ev["status"] != "unindexed_real" and not ev.get("miscited_real_case") and is_official_state(c):
            yr = (ev.get("paren") or [None, None])[1]
            band = ev.get("year_band") or {}
            if (yr and yr < 1950) or (band.get("hi") and band["hi"] < 1950):
                ev = dict(ev, status="unindexed_real", route="old_official_unindexed",
                          old_official=True, hit={"route": "old_official_unindexed", "cluster_id": None})
        if ev:
            reconciliation.append(ev)
        (unindexed if ev and ev["status"] == "unindexed_real" else still_fab).append((c, ev))
    fab_keys = {key(c) for c, _ in still_fab}
    unindexed_auth = {}          # authority id -> evidence; same case twice counts once
    seen_keys = {}
    for c, ev in unindexed:
        hid = (ev.get("hit") or {}).get("cluster_id")
        if hid and hid in by_cluster:
            continue             # already cited (and counted) through an indexed parallel cite
        k = key(c)
        if k in seen_keys:       # same volume/page written two ways ("65 N.Y.2d 189" / "65 NY2d 189")
            continue
        seen_keys[k] = True
        unindexed_auth.setdefault(hid or k, ev)
    unindexed_cids = [k for k in unindexed_auth if isinstance(k, int)]
    verified, mismatched, n_partial, name_guard_overrides = [], [], 0, []
    for cid, group in by_cluster.items():
        verdicts = []
        for g in group:
            pc = g.get("party_check") or {}
            v = pc.get("verdict")
            if v == "mismatch":
                # grader-side guard for check_brief false mismatches (initials 'P.T.' vs corpus 'Pt', short
                # corpus names 'Commerce v. Equity', acronyms 'HRS'): compare check_brief's claimed parties AND
                # the grader's own re-extraction of the name the answer wrote before the cite.
                resolved = [pc.get("resolved_name"), (g.get("case") or {}).get("case_name")]
                cl = pc.get("claimed") or {}
                claims = [(cl.get("lhs"), cl.get("rhs")), claimed_name(g, answer, use_claimed=False)]
                if any(c and r and names_equivalent(c, r) for c in claims for r in resolved):
                    v = "match_guard"
                    name_guard_overrides.append({"raw": g.get("raw"), "claimed": cl, "grader_claimed": claims[1],
                                                 "resolved_name": pc.get("resolved_name")})
            verdicts.append(v)
        # a cluster is a mismatch only if every claimed name for it mismatched
        if verdicts and all(v == "mismatch" for v in verdicts):
            mismatched.append(cid)
        else:
            verified.append(cid)
            n_partial += any(v == "partial" for v in verdicts)

    quote_verdicts = {}
    n_red = n_yellow = 0
    for cid in verified:
        group = by_cluster[cid]
        flag = next(((g.get("treatment") or {}).get("flag_color") for g in group if g.get("treatment")), None)
        n_red += flag == "red"
        n_yellow += flag == "yellow"
        for g in group:
            for qc in g.get("quote_checks") or []:
                v = qc.get("verdict")
                quote_verdicts[v] = quote_verdicts.get(v, 0) + 1

    skipped_spans = []
    quotes = extract_quotes(answer, skipped_spans)
    quote_results = []
    if quotes:
        names = {}
        for cid, grp in by_cluster.items():
            names[cid] = next(((g.get("case") or {}).get("case_name") for g in grp if g.get("case")), None)
        for c, ev in unindexed:
            h = ev.get("hit") or {}
            if h.get("cluster_id"):
                names.setdefault(h["cluster_id"], h.get("case_name"))
        prepared = {}
        if len(_PREP) > 300:          # bound memory over a full regrade (thousands of opinions)
            _PREP.clear()
            _GRAMS.clear()
        if fetch_text:
            # every resolved case the answer cites: the name verdict and the quote verdict are independent
            for cid in verified + mismatched + unindexed_cids:
                if cid not in _PREP:
                    t = fetch_text(cid)
                    _PREP[cid] = prep_opinion(t) if t else None
                if _PREP[cid]:
                    prepared[cid] = _PREP[cid]
        quote_results = [match_quote(qt, prepared, names) for qt in quotes]
    absent_quotes = [r["quote"] for r in quote_results if r["verdict"] == "absent"]
    n_quote_absent = len(absent_quotes)
    kinds = {}
    for r in quote_results:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1

    gold_keys = cite_keys(q.get("gold_citation") or "") if q else set()
    gold_cid = (q or {}).get("gold_cluster_id")
    gold_hit = 0
    for cid in verified:
        if gold_cid and str(cid) == str(gold_cid):
            gold_hit = 1
        for g in by_cluster[cid]:
            if (g.get("volume"), norm_reporter(g.get("reporter")), g.get("page")) in gold_keys:
                gold_hit = 1

    for c, ev in unindexed:
        hid = (ev.get("hit") or {}).get("cluster_id")
        if (gold_cid and hid and str(hid) == str(gold_cid)) or key(c) in gold_keys:
            gold_hit = 1

    n_cites = len(by_cluster) + len(fab_keys) + len(unindexed_auth)
    abstained = int(n_cites == 0 and bool(ABSTAIN_RE.search(answer or "")))
    stats = body.get("stats") or {}
    meta = {"verified_clusters": verified, "mismatch_clusters": mismatched,
            "fabricated_raw": [c.get("raw") for c, _ in still_fab],
            "unindexed_real_raw": [c.get("raw") for c, _ in unindexed],
            "unresolved_before_reconciliation": [c.get("raw") for c in fabricated],
            "reconciliation": reconciliation,
            "parallel_unresolved_raw": [c.get("raw") for c in parallel], "parallel_chain_lead": lead_of,
            "subsequent_history_raw": [c.get("raw") for c in history],
            "retracted_raw": [c.get("raw") for c in retracted_c],
            "court_propagated_miscite": [ev.get("raw") for c, ev in still_fab
                                         if ev and ev.get("miscited_real_case")
                                         and (ev.get("cite_corroborated_by_courts") or 0) >= 2],
            "n_partial": n_partial,
            "fabricated_near_miss": [c.get("raw") for c, _ in still_fab if c.get("did_you_mean")], "check_brief_quote_verdicts": quote_verdicts,
            "quotes_extracted": quotes, "quote_spans_skipped": skipped_spans,
            "name_guard_overrides": name_guard_overrides, "quotes_absent": absent_quotes,
            "quote_results": quote_results,
            "quote_absent_kind": {k: v for k, v in kinds.items() if k in ("paraphrase_in_quotes", "fabricated")},
            "quote_found_kind": {k: v for k, v in kinds.items() if k in ("verbatim", "near")},
            "n_quote_paraphrase": kinds.get("paraphrase_in_quotes", 0),
            "truncated_bytes": stats.get("truncated_bytes", 0),
            "resolved_by_name_server": [c.get("raw") for c in name_year],
            "stats_resolved_by_name": stats.get("resolved_by_name"),
            "grader_version": GRADER_VERSION,
            "n_statutes": ((body.get("statutes") or {}).get("stats") or {}).get("extracted", 0),
            "gold_found_in_question": bool(q)}
    return {"n_cites": n_cites, "n_verified": len(verified), "n_fabricated": len(fab_keys),
            "n_unindexed": len(unindexed_auth),
            "n_name_mismatch": len(mismatched), "n_quote_absent": n_quote_absent,
            "n_red": n_red, "n_yellow": n_yellow, "gold_hit": gold_hit, "abstained": abstained, "warned_treatment": warned(answer)}, meta


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", default=None, help="grade only this run (default: all)")
    ap.add_argument("--regrade", action="store_true", help="re-grade answers that already have grades")
    ap.add_argument("--questions", default=None, help="question file(s) holding gold fields, comma-separated")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--db", default=None)
    a = ap.parse_args()

    con = open_db(a.db) if a.db else open_db()
    gold = load_gold(con, a.questions.split(",") if a.questions else None)

    sql = ("SELECT a.run_id, a.qid, a.raw_answer FROM answers a "
           + ("" if a.regrade else "LEFT JOIN grades g ON g.run_id=a.run_id AND g.qid=a.qid ")
           + "WHERE a.error IS NULL AND a.raw_answer IS NOT NULL "
           + ("" if a.regrade else "AND g.qid IS NULL ")
           + ("AND a.run_id=? " if a.run_id else "") + "ORDER BY a.run_id, a.qid")
    todo = con.execute(sql, (a.run_id,) if a.run_id else ()).fetchall()
    print(f"to grade: {len(todo)}")
    if not todo:
        return
    token = load_keys().get("SYFERT_MCP_TOKEN")
    tls = threading.local()
    lock = threading.Lock()

    text_cache = {}
    recon_cache = {}

    def fetch_text(cid):
        """Full opinion text for a cluster via get_case (paged, <= 4 x 150k chars), cached per process."""
        if cid in text_cache:
            return text_cache[cid]
        if len(text_cache) > 300:
            with lock:
                text_cache.clear()
        parts, offset = [], 0
        for _ in range(4):
            try:
                raw, is_err, _ = tls.c.call_tool("get_case", {"cluster_id": int(cid), "include_text": True,
                                                              "max_chars": 150000, "offset": offset})
                ot = (json.loads(raw).get("opinion_text") or {}) if not is_err else {}
            except (MCPError, json.JSONDecodeError, ValueError):
                break
            parts.append(ot.get("text") or "")
            if not ot.get("truncated") or not ot.get("next_offset"):
                break
            offset = ot["next_offset"]
        with lock:
            text_cache[cid] = "".join(parts)
        return text_cache[cid]

    def work(row):
        run_id, qid, ans = row
        if not hasattr(tls, "c"):
            tls.c = MCPClient(token)
        sent = strip_md(ans)
        try:
            text, is_err, structured = tls.c.call_tool("check_brief", {"text": sent})
            if is_err:
                return row, None, f"check_brief isError: {text[:200]}"
            body = structured or json.loads(text)
        except (MCPError, json.JSONDecodeError) as e:
            return row, None, str(e)
        qrow = gold.get(qid) or {}

        def call_json(name, args):
            raw, is_err, _ = tls.c.call_tool(name, args)
            if is_err:
                raise MCPError(raw[:200])
            return json.loads(raw)

        def reconcile_fn(c):
            ck = (c.get("volume"), c.get("reporter"), c.get("page"), json.dumps(c.get("claimed")), qrow.get("state"))
            with lock:
                if ck in recon_cache:
                    return recon_cache[ck]
            ev = reconcile(c, sent, qrow.get("state"), call_json)
            with lock:
                recon_cache[ck] = ev
            return ev

        g, meta = summarize(sent, body, qrow or None, fetch_text, reconcile_fn)
        meta["sent_text"] = sent
        body["_citebench"] = meta
        with lock:
            con.execute("INSERT OR REPLACE INTO grades (run_id, qid, n_cites, n_verified, n_fabricated, "
                        "n_unindexed, n_name_mismatch, n_quote_absent, n_red, n_yellow, gold_hit, abstained, "
                        "warned_treatment, grader_version, check_brief_json) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (run_id, qid, g["n_cites"], g["n_verified"], g["n_fabricated"], g["n_unindexed"],
                         g["n_name_mismatch"], g["n_quote_absent"], g["n_red"], g["n_yellow"], g["gold_hit"],
                         g["abstained"], g["warned_treatment"], GRADER_VERSION, json.dumps(body)))
            con.commit()
        return row, (g, meta), None

    with cf.ThreadPoolExecutor(max_workers=min(4, a.concurrency)) as ex:
        for (run_id, qid, _), res, err in ex.map(work, todo):
            if err:
                print(f"  {run_id} {qid}: GRADE ERROR {err}")
                continue
            g, meta = res
            extra = f" TRUNCATED {meta['truncated_bytes']}B" if meta["truncated_bytes"] else ""
            nogold = "" if meta["gold_found_in_question"] else " (no gold row found)"
            print(f"  {run_id} {qid}: cites={g['n_cites']} ver={g['n_verified']} fab={g['n_fabricated']} "
                  f"unidx={g['n_unindexed']} name_mm={g['n_name_mismatch']} quote_bad={g['n_quote_absent']} red={g['n_red']} "
                  f"yel={g['n_yellow']} gold_hit={g['gold_hit']} abstain={g['abstained']} "
                  f"warned={g['warned_treatment']}{extra}{nogold}")


if __name__ == "__main__":
    main()
