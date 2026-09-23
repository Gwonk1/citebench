#!/usr/bin/env python3
# usage: python3 grade.py [--run-id RUN_ID] [--regrade [--reuse-check-brief [--reuse-quotes]]] [--dry-run] [--text-cache FILE] [--questions FILE] [--concurrency N]
"""Grade every ungraded answer by sending the raw answer text to the Syfert MCP check_brief tool.

Mapping of check_brief output (observed 2026-09-22, server syfert-legal-research 1.1.0) to grades:
  body = {mode, stats{extracted,resolved,unresolved,red,yellow,green,...,party_mismatch?,misquote?,
          truncated_bytes?}, warnings[], cites[], statutes{...}}
  each cite: raw, volume, reporter, page, pin, offsets[], cluster_id (null = not in corpus),
             case{case_name,...}|absent, treatment{flag_color,...}, claimed{lhs,rhs},
             party_check{verdict: match|partial|mismatch, resolved_name}|null,
             quote_checks[{brief_quote,best_match,percent,verdict}], did_you_mean[] (unresolved only)
  --reuse-quotes (g8, with --regrade --reuse-check-brief): keep each row's stored g7+ quote verdicts and gold_equivalent,
  fetch no opinion / rule text: zero MCP calls. Only quote attribution is re-derived (an 'unattributed' quote whose
  attached cite is now a g8 pin reference goes back to absent, g8_reattached). --dry-run writes nothing and prints
  each row whose counts differ from its stored grade.
  --regrade --reuse-check-brief (g7 re-grade): each row is re-summarized from its STORED check_brief body and stored
  reconciliation evidence; no check_brief call and no reconcile.py corpus lookup, so only the grader changes.
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
    * g8 PIN REFERENCES (pin_reference_g8): an UNRESOLVED cite still fabricated after reconciliation whose (volume,
      reporter) equals a RESOLVED cite's in the same answer and whose page lies after that authority's first page is a
      bare pinpoint into it ("Reporter Citation: 223 So. 2d 100 ... Pinpoint: 223 So. 2d 102"; "At 256 Mich App 3"):
      folded into that authority (not a new cite, not fabricated), listed in _citebench.pin_reference (raw,
      cluster_id, case_name, anchor_raw, delta, route) and counted per row in n_pin_reference. Routes:
      did_you_mean_same_cluster (check_brief's did_you_mean names the cited case itself, page - first <= 150) or
      page_within_60 (page - first <= 60 and did_you_mean does NOT place the page inside a different case that
      begins after the authority's first page, as "776 So. 2d 240" -> Glock v. Moore at 243 does not). A cite with
      a claimed case name sharing no party word with the authority is never a pin;
    * g8 NEAR MISSES (near_miss_g8, tag only, still fabricated): _citebench.near_miss lists {raw, kind, cluster_id,
      case_name, delta, via} per distinct fabricated cite: kind 'reporter_series' when the volume/page is, within 60
      pages, a cited (or the gold) case's cite in another series of the same reporter ("180 So. 2d 524" for American
      Bakeries, 180 So. 524); else 'interior_page' when did_you_mean places the page 1-60 pages inside a case the
      answer does NOT cite ("477 U.S. 248" for Anderson v. Liberty Lobby, 477 U.S. 242). A page before a
      did_you_mean case's first page (it falls in an earlier case) or no did_you_mean at all gives no near_miss.
      report.py near_miss_share = near misses / n_fabricated.
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
                    g7 (match_quote_g7 / rule_text_g7 / non_quote_reason_g7 / attached_cite_g7; the same five rules as
                    the Brief Check lib's BC5_20260923 pass, tools/bc5/APPLY.md), run ONLY on a quote the g5 matcher
                    calls absent: (a) typography folded and line-wrap hyphens joined on both sides ("dis-\ncretion");
                    (b) bracketed alterations optional (as written / free-standing [groups] dropped / all dropped);
                    (c) every citation inside the quote (reporter cites with names, dot-less NY/Mich. cites,
                    parentheticals holding a cite, Id., a dangling "see") is a split point, like an ellipsis; the parts
                    (>= 4 words) must appear IN ORDER in one cited opinion, a part after a citation within 250 chars of
                    the one before, a part under 20 words verbatim -> found (verbatim|near, with g7_rules);
                    (d) rule text: the lib's fixed list of the most-quoted rule sentences (Fed. R. Civ. P. 56(a)/(c),
                    12(b)(6), 12(d), 8(a)(2), 15(a)(2); Fed. R. Evid. 401/403 current and old = MRE 403; Fla. Stat.
                    90.403; Fla. R. Civ. P. 1.510) plus get_statute text of any Fed. R. / MRE / MCR / Fla. R. /
                    Fla. Stat. cite the answer names within 600 chars of the quote -> verdict/kind 'rule_text';
                    (e) at extraction, a span that is subsequent history / a treatment phrase ("overruled on other
                    grounds by ...") or sits inside a docket / WL cite's parenthetical -> verdict 'skipped', kind
                    'skipped_non_quote' (this can also move a g6 'found' span; no count uses it).
                    A quote still absent whose attached citation (the next cite within 250 chars in its paragraph, else
                    a cite ending <= 120 chars before it) has no cluster (fabricated / unindexed without a hit) or is a
                    docket / WL cite, or an answer with no resolved cited opinion text at all -> verdict/kind
                    'unattributed', counted in n_quote_unattributed, NOT in n_quote_absent.
  n_quote_unattributed = g7: quotes not found in any cited opinion whose own citation has no cluster (see above).
  n_red / n_yellow= verified authorities whose treatment.flag_color is red / yellow
  gold_hit        = 1 if a verified authority has cluster_id == gold_cluster_id, or its
                    (volume, reporter, page) equals one parsed from gold_citation
  gold_equivalent = g7: 1 if gold_hit, or if a verified (or unindexed-with-cluster) cited opinion's text contains a
                    >= 12-word verbatim run of the question's proposition (the whole proposition when it has 6-11
                    words; digit tokens dropped, g7 typography applied); evidence in _citebench.gold_equivalent_evidence.
                    Text rule only: the "cites gold for that passage" arm is NOT used, because get_citing_cases cannot
                    say which passage a citer cites gold for (and caps at 100 citers); a citer that quotes the
                    proposition is already caught by the text rule.
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
import sqlite3
import threading
import zlib

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
GRADER_VERSION = "g8-pinref-20260923"

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


def _strip_cites(t, repl=" ", v_nodot=False):
    """Remove citations: each reporter cite / Id. / citing-parenthetical match, and, for a reporter cite, the
    'Name v. Name,' in front of it (found by walking tokens backwards, no regex backtracking). g7: repl replaces each
    citation (default one space, as before); v_nodot also accepts a dot-less 'v' (New York style) in the name."""
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
                if w in ("v.", "vs.") or (v_nodot and w in ("v", "vs")):
                    seen_v = True
                elif not (w[:1].isupper() or w.lower() in _NAME_CONNECT):
                    break
                k -= 1
            if seen_v and k < len(toks):
                start = max(last, start - 160) + toks[k].start()
        out.append(t[last:start])
        out.append(repl)
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



# --- g7 quote-matcher rules (2026-09-23). The same five rules as the Brief Check lib's BC5_20260923 pass
# (tools/bc5/APPLY.md). (a)-(d) run ONLY for a quote match_quote() calls absent, so no g6 'found' changes there;
# (e) runs at extraction and can also turn a g6 'found' span into skipped_non_quote (no count uses either).
#  (a) typography on both sides: soft hyphens / zero-width marks dropped, Unicode hyphens, odd spaces and curly quotes
#      folded, a word broken by a line-wrap hyphen joined ("dis-\ncretion", "dis- cretion");
#  (b) bracketed alterations optional: the quote as written, with free-standing [groups] dropped, with every group
#      dropped ("[t]he first principle gleaned from the [Steelworkers] Trilogy");
#  (c) citations in the quote become split points (reporter cites with names, dot-less NY/Mich. cites, parentheticals
#      holding a cite, Id., a dangling "see"), ellipses split as before; the parts (>= 4 words) must appear IN ORDER in
#      one opinion, a part after a citation within 250 chars of the previous part, a part under 20 words verbatim
#      (the 80% run allowance only for longer parts);
#  (d) rule text: a quote still absent is tested against G7_RULE_TEXTS (the lib's fixed list) and against the text of
#      any Fed. R. / MRE / MCR / Fla. R. / Fla. Stat. cite the answer names within 600 chars of the quote (MCP
#      get_statute); a match is kind 'rule_text', not absent;
#  (e) non-quote spans (subsequent history / treatment phrases, text inside a docket or WL cite's parenthetical) are
#      kind 'skipped_non_quote', not absent.
# A quote still absent whose attached citation (the next cite within 250 chars in its paragraph, else a cite ending
# <= 120 chars before it) has no cluster, or is a docket / WL cite, is kind 'unattributed' (n_quote_unattributed), not
# absent: it could not be checked against its source. With no resolved cited opinion at all every quote is unattributed.
G7_RULE_TEXTS = [
    ("Fed. R. Civ. P. 56(a) (2010-); Fla. R. Civ. P. 1.510(a) (2021-)",
     "The court shall grant summary judgment if the movant shows that there is no genuine dispute as to any material "
     "fact and the movant is entitled to judgment as a matter of law."),
    ("Fed. R. Civ. P. 56(c) (before 2007); Fla. R. Civ. P. 1.510(c) (before 2021)",
     "The judgment sought shall be rendered forthwith if the pleadings, depositions, answers to interrogatories, and "
     "admissions on file, together with the affidavits, if any, show that there is no genuine issue as to any material "
     "fact and that the moving party is entitled to a judgment as a matter of law."),
    ("Fed. R. Civ. P. 56(c)(2) (2007-2010)",
     "The judgment sought should be rendered if the pleadings, the discovery and disclosure materials on file, and any "
     "affidavits show that there is no genuine issue as to any material fact and that the movant is entitled to "
     "judgment as a matter of law."),
    ("Fed. R. Civ. P. 12(b)(6)", "failure to state a claim upon which relief can be granted"),
    ("Fed. R. Civ. P. 12(d)",
     "If, on a motion under Rule 12(b)(6) or 12(c), matters outside the pleadings are presented to and not excluded by "
     "the court, the motion must be treated as one for summary judgment under Rule 56."),
    ("Fed. R. Civ. P. 8(a)(2)", "a short and plain statement of the claim showing that the pleader is entitled to relief"),
    ("Fed. R. Civ. P. 15(a)(2)", "The court should freely give leave when justice so requires."),
    ("Fed. R. Evid. 403 (2011-); MRE 403 (2024-)",
     "The court may exclude relevant evidence if its probative value is substantially outweighed by a danger of one or "
     "more of the following: unfair prejudice, confusing the issues, misleading the jury, undue delay, wasting time, or "
     "needlessly presenting cumulative evidence."),
    ("Fed. R. Evid. 403 (before 2011); MRE 403 (before 2024)",
     "Although relevant, evidence may be excluded if its probative value is substantially outweighed by the danger of "
     "unfair prejudice, confusion of the issues, or misleading the jury, or by considerations of undue delay, waste of "
     "time, or needless presentation of cumulative evidence."),
    ("Fla. Stat. § 90.403",
     "Relevant evidence is inadmissible if its probative value is substantially outweighed by the danger of unfair "
     "prejudice, confusion of issues, misleading the jury, or needless presentation of cumulative evidence."),
    ("Fed. R. Evid. 401 (2011-)",
     "Evidence is relevant if: (a) it has any tendency to make a fact more or less probable than it would be without "
     "the evidence; and (b) the fact is of consequence in determining the action."),
    ("Fed. R. Evid. 401 (before 2011)",
     "\"Relevant evidence\" means evidence having any tendency to make the existence of any fact that is of consequence "
     "to the determination of the action more probable or less probable than it would be without the evidence."),
]
G7_NORM = [(re.compile("[­​-‍⁠﻿]"), ""), (re.compile("[‐‑]"), "-"),
           (re.compile("[  -   　]"), " "), (re.compile("[‘’ʼ]"), "'"),
           (re.compile("[“”]"), '"'),
           (re.compile(r"(?<=[a-z])-[ \t]*\r?\n[ \t]*(?=[a-z])"), ""), (re.compile(r"(?<=[a-z])-[ \t]+(?=[a-z])"), "")]
CITE_MARK = "‥"
_G7_CORE = re.compile(r"\b\d{1,4}\s+[A-Z][\w.'’]{0,10}(?:\s[\w.'’]{1,10}){0,3}\s+\d{1,5}\b")
_G7_PAREN = re.compile(r"\((?:[^()]|\([^()]*\))*\)")
_G7_NAME_TOK = r"[A-Z][\w'’.&-]*"
_G7_DOTLESS = re.compile(
    r"(?:\b" + _G7_NAME_TOK + r"(?:\s+(?:" + _G7_NAME_TOK + r"|of|the|&)){0,5}\s+v\.?\s+" + _G7_NAME_TOK
    + r"(?:\s+(?:" + _G7_NAME_TOK + r"|of|the|&)){0,6},?\s+)?"
    r"\b\d{1,4}\s+(?:(?:NY|AD|Misc|NYS|NE|NW|SE|SW|So|A|P|F)\s?[2-4]d|NY|US|Mich(?:\s+App)?|Pa|Ill(?:\s+App)?|Ohio\s+St|Wis|Minn)"
    r"\s+\d{1,5}\b(?:\s*,\s*\d{1,5}\b(?!\s+[A-Z]))*")
_G7_DANGLING = re.compile("‥[\\s,;:.]*(?:see\\s+also|see|cf\\.|accord|but\\s+see|and)?[\\s,;:.]*(?=[‥…]|$)", re.I)
_G7_SPLIT = re.compile("(\\.\\s*\\.\\s*\\.|…|\\[\\s*\\.\\.\\.\\s*\\]|‥)")
_G7_HISTORY = re.compile(
    r"^\W*(?:(?:overruled|abrogated|superseded|disapproved(?:\s+of)?|receded\s+from|called\s+into\s+(?:doubt|question)|"
    r"questioned|vacated|modified)(?:\s+in\s+part)?(?:,?\s+on\s+other\s+grounds)?,?\s+(?:by|as\s+stated\s+in|"
    r"as\s+recognized\s+in)\b|(?:overruled|abrogated|superseded|disapproved|reversed|vacated|modified|questioned)"
    r"(?:\s+in\s+part)?,?\s+on\s+other\s+grounds\b|(?:aff|rev)['’]?d\b|on\s+other\s+grounds\b|"
    r"(?:cert\.?|certiorari|reh['’]?g\.?|rehearing|review)\s+(?:denied|granted|dismissed)\b)", re.I)
_G7_NOREPORTER = re.compile(r"(?:\bNo\.\s*[\w:.\-]{2,}|\b(?:19|20)\d{2}\s+WL\s+\d+|\bLEXIS\s+\d+|\bslip\s+op\.?)"
                            r"[^()]{0,60}(?:\([^()]{0,80}\))?\s*$")
_G7_NOREPORTER_ANY = re.compile(r"\bNo\.\s*[\w:.\-]*\d|\b(?:19|20)\d{2}\s+WL\s+\d+|\bLEXIS\s+\d+|\bslip\s+op\b")
_G7_RULE_CITE = [
    (re.compile(r"\bFed\.?\s*R\.?\s*Civ\.?\s*P\.?\s*(\d+)|\bFRCP\s*(\d+)", re.I), "fedrule", "Fed. R. Civ. P. {}"),
    (re.compile(r"\bFed\.?\s*R\.?\s*Evid\.?\s*(\d+)|\bFRE\s*(\d+)"), "fedrule", "Fed. R. Evid. {}"),
    (re.compile(r"\bFed\.?\s*R\.?\s*Crim\.?\s*P\.?\s*(\d+)", re.I), "fedrule", "Fed. R. Crim. P. {}"),
    (re.compile(r"\bFed\.?\s*R\.?\s*App\.?\s*P\.?\s*(\d+)", re.I), "fedrule", "Fed. R. App. P. {}"),
    (re.compile(r"\bMRE\s*(\d+)|\bMich\.?\s*R\.?\s*Evid\.?\s*(\d+)"), "mi", "MRE {}"),
    (re.compile(r"\bMCR\s*(\d+\.\d+)"), "mi", "MCR {}"),
    (re.compile(r"\bFla\.?\s*R\.?\s*(?:Civ|Crim|App|Jud|Gen)\.?\s*(?:P\.?|Admin\.?)?\s*(\d\.\d+)"), "fl_rule", "{}"),
    (re.compile(r"§\s*(\d+\.\d+)[^.;]{0,12}Fla\.\s*Stat|Fla\.\s*Stat\.\s*§\s*(\d+\.\d+)"), "fl_statute", "{}"),
]
_G7_BARE_RULE = re.compile(r"\bRule\s+(\d+)\s*\(", re.I)


def g7_norm(t):
    for rx, rep in G7_NORM:
        t = rx.sub(rep, t)
    return t


def prep_opinion_g7(raw):
    """-> (plain, cite_stripped) haystacks of the g7-normalised text (same cleaning as prep_opinion)."""
    t = STAR_PAGE_RE.sub(" ", g7_norm(raw or ""))
    return " " + " ".join(_match_words(t)) + " ", " " + " ".join(_match_words(_strip_cites(t))) + " "


def _bracket_variants(q):
    if "[" not in q:
        return []
    out = []
    for rx in (r"(?<![A-Za-z0-9])\[[^\[\]]{1,60}\](?![A-Za-z0-9])", r"\[[^\[\]]{0,60}\]"):
        v = re.sub(rx, " ", q)
        if v != q and v not in out:
            out.append(v)
    return out


def _cite_split(q):
    """(c): every citation in the quote -> a CITE_MARK split point."""
    m = f" {CITE_MARK} "
    q = _G7_PAREN.sub(lambda p: m if _G7_CORE.search(p.group(0)) else p.group(0), q)
    q = _G7_DOTLESS.sub(m, q)
    q = _strip_cites(q, repl=m, v_nodot=True)
    return _G7_DANGLING.sub(CITE_MARK + " ", q)


def _g7_variants(quote):
    """-> [(prepared quote, rules)] for the as-written quote and its bracket variants."""
    out = []
    for v, rules in [(quote, [])] + [(b, ["brackets_optional"]) for b in _bracket_variants(quote)]:
        q = g7_norm(EDITORIAL_RE.sub(" ", v))
        s = _cite_split(q)
        out.append((s, ["typography"] + rules + (["citations_split"] if CITE_MARK in s else [])))
    return out


def _g7_segments(q):
    segs, near = [], False
    for i, part in enumerate(_G7_SPLIT.split(q)):
        if i % 2:
            near = near or part == CITE_MARK
            continue
        w = _match_words(part)
        if len(w) >= 4:
            segs.append((w, near and bool(segs)))
            near = False
    return segs


def _ordered_found(segs, hay):
    """-> 'verbatim' | 'near' | None: every part in order, a part after a citation within 250 chars, a part under
    20 words verbatim (longer: a contiguous run of >= 80% of its words)."""
    if not segs:
        return None
    pos, kinds = 0, []
    for w, near in segs:
        n = len(w)
        need = n if n < 20 else max(4, int(0.8 * n + 0.999))
        hit = None
        for size in range(n, need - 1, -1):
            for i in range(0, n - size + 1):
                run = " " + " ".join(w[i:i + size]) + " "
                p = hay.find(run, pos)
                if p >= 0 and near and p - pos > 250:
                    p = -1
                if p >= 0:
                    hit = (size, p + len(run) - 1)
                    break
            if hit:
                break
        if not hit:
            return None
        kinds.append("verbatim" if hit[0] == n else "near")
        pos = hit[1]
    return "verbatim" if all(k == "verbatim" for k in kinds) else "near"


def match_quote_g7(quote, prepared7):
    """(a)(b)(c) extra pass. prepared7: {cluster_id: (plain, cite_stripped)} g7 haystacks. -> (kind, cid, rules)|None."""
    best = None
    for q, rules in _g7_variants(quote):
        segs = _g7_segments(q)
        for cid, hays in prepared7.items():
            for lvl, hay in enumerate(hays):
                k = _ordered_found(segs, hay)
                if k and (best is None or (k == "verbatim" and best[0] == "near")):
                    best = (k, cid, rules + (["opinion_citations_stripped"] if lvl else []))
                if best and best[0] == "verbatim":
                    return best
    return best


def rule_text_g7(quote, answer, fetch_rule=None):
    """(d) -> {rule, via, passage?} or None. The fixed list first, then get_statute for rule/statute cites the answer
    names within 600 chars of the quote (fetch_rule(jurisdiction, citation) -> text or '')."""
    variants = [_g7_segments(q) for q, _ in _g7_variants(quote)]
    for label, text in G7_RULE_TEXTS:
        hay = " " + " ".join(_match_words(g7_norm(text))) + " "
        if any(_ordered_found(s, hay) for s in variants):
            return {"rule": label, "via": "fixed_list"}
    if not fetch_rule:
        return None
    p = answer.find(quote)
    near = answer[max(0, p - 600):p + len(quote) + 600] if p >= 0 else ""
    wanted = []
    for rx, jur, fmt in _G7_RULE_CITE:
        for m in rx.finditer(near):
            num = next(g for g in m.groups() if g)
            wanted.append((jur, fmt.format(num)))
    if not wanted:
        for m in _G7_BARE_RULE.finditer(near):
            wanted.append(("fedrule", f"Fed. R. Civ. P. {m.group(1)}"))
    for jur, cite in list(dict.fromkeys(wanted))[:4]:
        text = fetch_rule(jur, cite) or ""
        if not text:
            continue
        hay = " " + " ".join(_match_words(g7_norm(text))) + " "
        if any(_ordered_found(s, hay) for s in variants):
            return {"rule": cite, "via": "get_statute", "jurisdiction": jur}
    return None


def non_quote_reason_g7(qt, text, start):
    """(e) why the quoted span is not a quotation at all (None = it may be one)."""
    if _G7_HISTORY.match(qt):
        return "subsequent history / treatment phrase, not a quotation"
    lo = max(0, start - 600)
    para = text.rfind("\n\n", lo, start)
    if para >= 0:
        lo = para + 2
    depth = 0
    for j in range(start - 2, lo - 1, -1):
        ch = text[j]
        if ch == ")":
            depth += 1
        elif ch == "(":
            if depth:
                depth -= 1
                continue
            if _G7_NOREPORTER.search(text[max(0, j - 200):j]):
                return "inside the parenthetical of a citation with no reporter (docket / WL / slip opinion)"
            break
    return None


def attached_cite_g7(answer, quote, cite_spans):
    """The citation a quote is attributed to: the first cite starting within 250 chars after it in its paragraph,
    else a cite ending <= 120 chars before it (the "Cite (\"...\")" / "Cite: \"...\"" forms). -> (has_cluster, raw)
    or ('no_reporter', text) for a docket / WL cite, or None."""
    a = answer.find(quote)
    if a < 0:
        return None
    b = a + len(quote)
    para_end = answer.find("\n\n", b)
    lim = min(b + 250, para_end if para_end >= 0 else len(answer))
    after = sorted((s, e, has, raw) for s, e, has, raw in cite_spans if b <= s < lim)
    gap_to = after[0][0] if after else lim
    nr = _G7_NOREPORTER_ANY.search(answer, b, gap_to)
    if nr:
        return ("no_reporter", nr.group(0))
    if after:
        return (after[0][2], after[0][3])
    para_start = answer.rfind("\n\n", 0, a)
    before = [(e, has, raw) for s, e, has, raw in cite_spans if max(a - 120, para_start) <= e <= a]
    if before:
        e, has, raw = max(before)
        return (has, raw)
    return None


def gold_equivalent_g7(q, cids, fetch_text):
    """1 + evidence when a cited opinion's text contains a >= 12-word verbatim run of the question's proposition
    (the whole proposition when it has 6-11 words)."""
    w = _match_words(g7_norm((q or {}).get("proposition") or ""))
    if len(w) < 6 or not fetch_text:
        return 0, None
    size = min(12, len(w))
    grams = {" " + " ".join(w[i:i + size]) + " " for i in range(len(w) - size + 1)}
    for cid in cids:
        t = fetch_text(cid)
        if not t:
            continue
        for hay in (prep_opinion(t)[0],) + prep_opinion_g7(t):
            hit = next((g for g in grams if g in hay), None)
            if hit:
                return 1, {"cluster_id": cid, "run": hit.strip()}
    return 0, None


_GRAMS = {}
_PREP = {}
_PREP7 = {}


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


def extract_quotes(text, skipped=None, nonquote=None):
    """Case quotations in an answer (g5). Double-quoted passages (straight quotes paired strictly in order per
    paragraph, plus curly quotes) of >= 6 words; single-quoted spans inside them are part of the outer quote.
    Single-quoted spans outside any double quote count only if >= 6 words AND a citation follows. Drafted text
    that is skipped (rule/statute cite inside) still contributes its INNER single-quoted passages. Each span
    must look like a case quotation (_skip_reason); de-duplicated by normalised text. `skipped` collects
    [span, reason] for audit. g7: `nonquote` (when given) collects [span, reason] for spans that pass those tests but
    are subsequent history / a docket cite's parenthetical (non_quote_reason_g7); they are not returned as quotes."""
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
        if nonquote is not None:
            nq = non_quote_reason_g7(qt, text, a)
            if nq:
                nonquote.append([qt, nq])
                return
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


# --- g8 pin references and near misses (2026-09-23) ------------------------------------------------------------
# A model that writes the full cite of a case and then, separately, a bare pinpoint "VOL REPORTER PAGE" whose PAGE is
# an interior page of that same opinion ("223 So. 2d 100 ... Pinpoint: 223 So. 2d 102") has made a citation-FORM slip,
# not invented a case. check_brief cannot resolve the bare pin (PAGE is not a first page) and offers the case in
# did_you_mean. g8 folds such a cite into the authority it pins (pin_reference_g8). A still-fabricated cite whose page
# the index places inside an UNCITED case, or whose volume/page is a cited (or the gold) case's cite in another series
# of the same reporter ("180 So. 2d 524" for "180 So. 524"), stays fabricated but is tagged near_miss_g8.
PIN_MAX_DELTA = 60          # heuristic page span of an opinion when did_you_mean does not name the case
PIN_MAX_DELTA_DYM = 150     # did_you_mean names the cited case itself: its first page is the nearest start to PAGE
SERIES_SUFFIX_RE = re.compile(r"(?:[2-9]d|\d(?:st|nd|rd|th))$")


def _page_int(x):
    try:
        return int(str(x).strip())
    except (TypeError, ValueError):
        return None


def _series_family(rep):
    """normalised reporter minus its series suffix: 'So. 2d' / 'So.' -> 'so', 'F.3d' -> 'f', 'F. Supp. 2d' -> 'fsupp'."""
    return SERIES_SUFFIX_RE.sub("", norm_reporter(rep))


def _claim_conflicts(c, name):
    """True when check_brief found a case name claimed for this cite that shares no party token with `name`
    ("Smith v. Jones, 223 So. 2d 104" next to Weimar at 100 is a different, invented case, not a pin)."""
    cl = c.get("claimed") or {}
    lhs, rhs = cl.get("lhs"), cl.get("rhs")
    if not (lhs or rhs) or not name:
        return False
    if lhs and rhs and names_equivalent((lhs, rhs), name):
        return False
    return not (set(_name_toks(f"{lhs or ''} {rhs or ''}")) & set(_name_toks(name)))


def pin_reference_g8(c, anchors):
    """c: an unresolved cite. anchors: resolved cites in the same answer. -> evidence dict when c is a bare pinpoint
    into one of them, else None. Same volume and reporter, PAGE after the anchor's first page, and either
    did_you_mean names the anchor's cluster (PAGE - first <= PIN_MAX_DELTA_DYM), or PAGE - first <= PIN_MAX_DELTA and
    did_you_mean does not place PAGE inside a different case beginning after the anchor's first page."""
    p = _page_int(c.get("page"))
    if p is None:
        return None
    vol, rep = str(c.get("volume")), norm_reporter(c.get("reporter"))
    cands = []
    for a in anchors:
        f = _page_int(a.get("page"))
        if f is not None and f < p and str(a.get("volume")) == vol and norm_reporter(a.get("reporter")) == rep:
            cands.append((p - f, a))
    if not cands:
        return None
    cands.sort(key=lambda t: t[0])
    dym = [(d.get("cluster_id"), _page_int(d.get("page"))) for d in c.get("did_you_mean") or []]

    def ev(delta, a, route):
        return {"raw": c.get("raw"), "cluster_id": a["cluster_id"], "case_name": (a.get("case") or {}).get("case_name"),
                "anchor_raw": a.get("raw"), "delta": delta, "route": route}

    for delta, a in cands:
        if delta <= PIN_MAX_DELTA_DYM and any(dc == a["cluster_id"] for dc, _ in dym) \
                and not _claim_conflicts(c, (a.get("case") or {}).get("case_name")):
            return ev(delta, a, "did_you_mean_same_cluster")
    delta, a = cands[0]
    if delta > PIN_MAX_DELTA or _claim_conflicts(c, (a.get("case") or {}).get("case_name")):
        return None
    if any(dc != a["cluster_id"] and dp is not None and p - delta < dp <= p for dc, dp in dym):
        return None          # the index says PAGE falls inside a different case that begins after the anchor
    return ev(delta, a, "page_within_%d" % PIN_MAX_DELTA)


def near_miss_g8(c, known_cites, cited_cids):
    """c: a cite still fabricated after g8 pins. known_cites: [(volume, normalised reporter, page, cluster_id,
    case_name, via)] of the cases the answer cites (plus gold). -> near_miss dict or None:
      reporter_series: same volume, a different series of the same reporter, PAGE within PIN_MAX_DELTA at or after
                       a known cite of a cited / gold case ("180 So. 2d 524" for American Bakeries, 180 So. 524);
      interior_page:   did_you_mean places PAGE inside a case NOT cited in the answer (its first page < PAGE,
                       PAGE - first <= PIN_MAX_DELTA): right volume, wrong page, e.g. "477 U.S. 248" for Anderson."""
    p = _page_int(c.get("page"))
    if p is None:
        return None
    vol, rep = str(c.get("volume")), norm_reporter(c.get("reporter"))
    fam = _series_family(c.get("reporter"))
    best = None
    for kv, krep, kp, kcid, kname, via in known_cites:
        kp = _page_int(kp)
        if kp is None or str(kv) != vol or krep == rep or SERIES_SUFFIX_RE.sub("", krep) != fam:
            continue
        if 0 <= p - kp <= PIN_MAX_DELTA and (best is None or p - kp < best["delta"]):
            best = {"raw": c.get("raw"), "kind": "reporter_series", "cluster_id": kcid, "case_name": kname,
                    "delta": p - kp, "via": via}
    if best:
        return best
    for d in c.get("did_you_mean") or []:
        dp = _page_int(d.get("page"))
        if dp is None or d.get("cluster_id") in cited_cids or not (0 < p - dp <= PIN_MAX_DELTA):
            continue
        if best is None or p - dp < best["delta"]:
            best = {"raw": c.get("raw"), "kind": "interior_page", "cluster_id": d.get("cluster_id"),
                    "case_name": d.get("case_name"), "delta": p - dp, "via": "did_you_mean"}
    return best


def summarize(answer, body, q, fetch_text=None, reconcile_fn=None, fetch_rule=None, stored_quotes=None):
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
    # g8: a bare pinpoint into a resolved authority of the same answer is that authority, not a new cite
    pin_refs, keep = [], []
    for c, ev in still_fab:
        pr = pin_reference_g8(c, all_resolved)
        (pin_refs.append((c, pr)) if pr else keep.append((c, ev)))
    still_fab = keep
    pin_keys = {key(c) for c, _ in pin_refs}
    fab_keys = {key(c) for c, _ in still_fab}
    cited_cids = {c["cluster_id"] for c in all_resolved}
    known = [(str(c.get("volume")), norm_reporter(c.get("reporter")), c.get("page"), c["cluster_id"],
              (c.get("case") or {}).get("case_name"), "cited") for c in all_resolved]
    if q and q.get("gold_cluster_id"):
        known += [(v, r, pg, q["gold_cluster_id"], q.get("gold_case_name"), "gold")
                  for v, r, pg in cite_keys(q.get("gold_citation") or "")]
    near_miss, nm_seen = [], set()
    for c, _ in still_fab:
        if key(c) in nm_seen:
            continue
        nm = near_miss_g8(c, known, cited_cids)
        if nm:
            nm_seen.add(key(c))
            near_miss.append(nm)
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

    def make_cite_spans():
        par_ids = {id(c) for c in parallel}
        unidx_cl = {id(c) for c, ev in unindexed if (ev.get("hit") or {}).get("cluster_id")}
        unidx_cl |= {id(c) for c, _ in pin_refs}     # g8: a pin reference is attributed to its authority
        return [(o, o + len(c.get("raw") or ""),
                 bool(c.get("cluster_id")) or id(c) in par_ids or id(c) in unidx_cl, c.get("raw"))
                for c in cites for o in char_offsets(answer, c)]

    cite_spans = None
    if stored_quotes is not None:
        # g8 --reuse-quotes: the stored g7 quote verdicts stand (no opinion / rule text is fetched). The only quote
        # decision a citation-side change can move is attribution: an 'unattributed' quote whose attached cite now
        # resolves (a g8 pin reference) goes back to absent with its g5 kind.
        quotes = list(stored_quotes.get("quotes_extracted") or [])
        skipped_spans = list(stored_quotes.get("quote_spans_skipped") or [])
        quote_results = json.loads(json.dumps(stored_quotes.get("quote_results") or []))
        for r in quote_results:
            if r.get("verdict") != "unattributed" or not str(r.get("unattributed_reason") or "").startswith(
                    "attached citation did not resolve"):
                continue
            if cite_spans is None:
                cite_spans = make_cite_spans()
            att = attached_cite_g7(answer, r["quote"], cite_spans)
            if att and att[0] is True:
                r.update(verdict="absent", g8_reattached=att[1],
                         kind="paraphrase_in_quotes" if (r.get("paraphrase_ratio") or 0) >= 0.6 else "fabricated")
                r.pop("unattributed_reason", None)
    else:
        skipped_spans, nonquote_spans = [], []
        quotes = extract_quotes(answer, skipped_spans, nonquote_spans)
        quote_results = []
        prepared, prepared7, names = {}, {}, {}
        if quotes:
            names = {}
            for cid, grp in by_cluster.items():
                names[cid] = next(((g.get("case") or {}).get("case_name") for g in grp if g.get("case")), None)
            for c, ev in unindexed:
                h = ev.get("hit") or {}
                if h.get("cluster_id"):
                    names.setdefault(h["cluster_id"], h.get("case_name"))
            if len(_PREP) > 300:          # bound memory over a full regrade (thousands of opinions)
                _PREP.clear()
                _PREP7.clear()
                _GRAMS.clear()
            if fetch_text:
                # every resolved case the answer cites: the name verdict and the quote verdict are independent
                for cid in verified + mismatched + unindexed_cids:
                    # g7: local copies -- another worker thread may clear the shared caches between these lines
                    e6, e7 = _PREP.get(cid, False), _PREP7.get(cid, False)
                    if e6 is False or e7 is False:
                        t = fetch_text(cid)
                        e6, e7 = (prep_opinion(t), prep_opinion_g7(t)) if t else (None, None)
                        _PREP[cid], _PREP7[cid] = e6, e7
                    if e6:
                        prepared[cid] = e6
                        prepared7[cid] = e7
            quote_results = [match_quote(qt, prepared, names) for qt in quotes]
        # g7: the extra passes, only for quotes match_quote() calls absent (every g6 'found' is unchanged)
        for r in quote_results:
            if r["verdict"] != "absent":
                continue
            hit = match_quote_g7(r["quote"], prepared7) if prepared7 else None
            if hit:
                r.update(verdict="found", kind=hit[0], cluster_id=hit[1], case_name=names.get(hit[1]), g7_rules=hit[2])
                r.pop("paraphrase_ratio", None)
                continue
            rt = rule_text_g7(r["quote"], answer, fetch_rule)
            if rt:
                r.update(verdict="rule_text", kind="rule_text", rule_text=rt)
                continue
            if not prepared:
                r.update(verdict="unattributed", kind="unattributed",
                         unattributed_reason="no resolved cited opinion text to search")
                continue
            if cite_spans is None:
                cite_spans = make_cite_spans()
            att = attached_cite_g7(answer, r["quote"], cite_spans)
            if att and att[0] is not True:
                r.update(verdict="unattributed", kind="unattributed",
                         unattributed_reason=("attached citation has no reporter: " if att[0] == "no_reporter"
                                              else "attached citation did not resolve to a case: ") + str(att[1]))
        quote_results += [{"quote": qt, "verdict": "skipped", "kind": "skipped_non_quote", "skipped_reason": why,
                           "searched": []} for qt, why in nonquote_spans]
    absent_quotes = [r["quote"] for r in quote_results if r["verdict"] == "absent"]
    n_quote_absent = len(absent_quotes)
    n_quote_unattributed = sum(r["verdict"] == "unattributed" for r in quote_results)
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

    # g7 gold_equivalent: gold_hit, or a verified / unindexed cited opinion holding a >= 12-word verbatim run of the
    # question's proposition (text rule only; see grade.py docstring)
    if gold_hit:
        gold_equiv, gold_equiv_ev = 1, {"route": "gold_hit"}
    else:
        if stored_quotes is not None and "gold_equivalent" in stored_quotes:   # g8 --reuse-quotes: verified set unchanged
            gold_equiv, gold_equiv_ev = stored_quotes["gold_equivalent"], stored_quotes.get("gold_equivalent_evidence")
        else:
            gold_equiv, gold_equiv_ev = gold_equivalent_g7(q, verified + unindexed_cids, fetch_text)
            if gold_equiv_ev:
                gold_equiv_ev["route"] = "proposition_run"

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
            "pin_reference": [pr for _, pr in pin_refs], "n_pin_reference": len(pin_keys), "near_miss": near_miss,
            "quotes_extracted": quotes, "quote_spans_skipped": skipped_spans,
            "name_guard_overrides": name_guard_overrides, "quotes_absent": absent_quotes,
            "quote_results": quote_results,
            "quote_absent_kind": {k: v for k, v in kinds.items() if k in ("paraphrase_in_quotes", "fabricated")},
            "quote_found_kind": {k: v for k, v in kinds.items() if k in ("verbatim", "near")},
            "quote_other_kind": {k: v for k, v in kinds.items() if k in ("rule_text", "skipped_non_quote", "unattributed")},
            "n_quote_unattributed": n_quote_unattributed, "gold_equivalent": gold_equiv,
            "gold_equivalent_evidence": gold_equiv_ev,
            "n_quote_paraphrase": kinds.get("paraphrase_in_quotes", 0),
            "truncated_bytes": stats.get("truncated_bytes", 0),
            "resolved_by_name_server": [c.get("raw") for c in name_year],
            "stats_resolved_by_name": stats.get("resolved_by_name"),
            "grader_version": GRADER_VERSION,
            "n_statutes": ((body.get("statutes") or {}).get("stats") or {}).get("extracted", 0),
            "gold_found_in_question": bool(q)}
    return {"n_cites": n_cites, "n_verified": len(verified), "n_fabricated": len(fab_keys),
            "n_unindexed": len(unindexed_auth), "n_pin_reference": len(pin_keys),
            "n_name_mismatch": len(mismatched), "n_quote_absent": n_quote_absent,
            "n_quote_unattributed": n_quote_unattributed,
            "n_red": n_red, "n_yellow": n_yellow, "gold_hit": gold_hit, "gold_equivalent": gold_equiv,
            "abstained": abstained, "warned_treatment": warned(answer)}, meta


GRADE_COLS = ("n_cites, n_verified, n_fabricated, n_unindexed, n_name_mismatch, n_quote_absent, n_quote_unattributed, "
              "n_red, n_yellow, gold_hit, gold_equivalent, abstained, warned_treatment, n_pin_reference")


class NoMCP:
    """--reuse-quotes: stands in for the MCP client so that no tool call can leave this process."""
    def call_tool(self, name, args):
        raise MCPError(f"--reuse-quotes makes no MCP calls (attempted {name})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", default=None, help="grade only this run (default: all)")
    ap.add_argument("--regrade", action="store_true", help="re-grade answers that already have grades")
    ap.add_argument("--reuse-check-brief", action="store_true",
                    help="with --regrade: re-summarize each row from its STORED check_brief body and stored "
                         "reconciliation evidence (no check_brief call, no reconcile.py corpus lookups), so a grader "
                         "change is measured alone; opinion / rule texts are still fetched with get_case / get_statute")
    ap.add_argument("--reuse-quotes", action="store_true",
                    help="with --reuse-check-brief (g8): also keep each row's STORED g7+ quote verdicts and gold_equivalent "
                         "instead of re-matching quotes, so no get_case / get_statute call is made either (zero MCP "
                         "calls); only quote attribution is re-derived from the new citation decisions")
    ap.add_argument("--dry-run", action="store_true",
                    help="grade but write nothing: print each row whose counts differ from its stored grade")
    ap.add_argument("--text-cache", default=None,
                    help="sqlite file caching get_case / get_statute texts across runs (created if absent)")
    ap.add_argument("--questions", default=None, help="question file(s) holding gold fields, comma-separated")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--db", default=None)
    a = ap.parse_args()
    if a.reuse_check_brief and not a.regrade:
        ap.error("--reuse-check-brief needs --regrade")
    if a.reuse_quotes and not a.reuse_check_brief:
        ap.error("--reuse-quotes needs --regrade --reuse-check-brief")

    con = open_db(a.db) if a.db else open_db()
    gold = load_gold(con, a.questions.split(",") if a.questions else None)

    if a.reuse_check_brief:
        import reconcile as _rc
        _rc.CBC_DB = _rc.CASES_DB = "/nonexistent/reuse-check-brief"   # never open a corpus DB in this mode
        sql = ("SELECT a.run_id, a.qid, a.raw_answer, g.check_brief_json, " + GRADE_COLS + " FROM answers a JOIN grades g "
               "ON g.run_id=a.run_id AND g.qid=a.qid WHERE a.error IS NULL AND a.raw_answer IS NOT NULL "
               + ("AND a.run_id=? " if a.run_id else "") + "ORDER BY a.run_id, a.qid")
    else:
        sql = ("SELECT a.run_id, a.qid, a.raw_answer, NULL, " + ", ".join("NULL" for _ in GRADE_COLS.split(",")) + " FROM answers a "
               + ("" if a.regrade else "LEFT JOIN grades g ON g.run_id=a.run_id AND g.qid=a.qid ")
               + "WHERE a.error IS NULL AND a.raw_answer IS NOT NULL "
               + ("" if a.regrade else "AND g.qid IS NULL ")
               + ("AND a.run_id=? " if a.run_id else "") + "ORDER BY a.run_id, a.qid")
    todo = con.execute(sql, (a.run_id,) if a.run_id else ()).fetchall()
    print(f"to grade: {len(todo)}" + (" (reusing stored check_brief bodies)" if a.reuse_check_brief else ""))
    if not todo:
        return
    token = load_keys().get("SYFERT_MCP_TOKEN")
    tls = threading.local()
    lock = threading.Lock()

    text_cache = {}
    recon_cache = {}
    rule_cache = {}
    counters = {"recon_live": 0, "sent_text_changed": 0, "changed": 0}
    disk = None
    if a.text_cache:
        disk = sqlite3.connect(a.text_cache, check_same_thread=False, timeout=30)
        disk.execute("CREATE TABLE IF NOT EXISTS texts (k TEXT PRIMARY KEY, z BLOB)")
        disk.commit()

    def disk_get(k):
        if disk is None:
            return None
        with lock:
            row = disk.execute("SELECT z FROM texts WHERE k=?", (k,)).fetchone()
        return zlib.decompress(row[0]).decode("utf-8") if row else None

    def disk_put(k, text):
        if disk is None:
            return
        with lock:
            disk.execute("INSERT OR REPLACE INTO texts VALUES (?,?)", (k, zlib.compress(text.encode("utf-8"), 6)))
            disk.commit()

    def fetch_text(cid):
        """Full opinion text for a cluster via get_case (paged, <= 4 x 150k chars), cached per process."""
        hit = text_cache.get(cid)   # g7: .get + locals -- another thread may clear the cache at any time
        if hit is not None:
            return hit
        cached = disk_get(f"case:{int(cid)}")
        if cached is not None:
            with lock:
                if len(text_cache) > 300:
                    text_cache.clear()
                text_cache[cid] = cached
            return cached
        if len(text_cache) > 300:
            with lock:
                text_cache.clear()
        parts, offset, ok = [], 0, True
        for _ in range(4):
            try:
                raw, is_err, _ = tls.c.call_tool("get_case", {"cluster_id": int(cid), "include_text": True,
                                                              "max_chars": 150000, "offset": offset})
                ot = (json.loads(raw).get("opinion_text") or {}) if not is_err else {}
            except (MCPError, json.JSONDecodeError, ValueError):
                ok = False
                break
            parts.append(ot.get("text") or "")
            if not ot.get("truncated") or not ot.get("next_offset"):
                break
            offset = ot["next_offset"]
        text = "".join(parts)
        with lock:
            text_cache[cid] = text
        if ok:
            disk_put(f"case:{int(cid)}", text)
        return text

    def fetch_rule(jur, cite):
        """g7 (d): the text of one rule / statute section via get_statute, cached ('' when absent)."""
        k = f"rule:{jur}|{cite}"
        with lock:
            if k in rule_cache:
                return rule_cache[k]
        text = disk_get(k)
        if text is None:
            try:
                raw, is_err, _ = tls.c.call_tool("get_statute", {"jurisdiction": jur, "citation": cite})
                d = json.loads(raw) if not is_err else {}
                b = d.get("body") or ""
                text = (b.get("text") or "") if isinstance(b, dict) else str(b)
                disk_put(k, text)
            except (MCPError, json.JSONDecodeError, ValueError):
                text = ""
        with lock:
            rule_cache[k] = text
        return text

    def rkey(raw):
        return re.sub(r"[\s.]+", "", raw or "").lower()

    def work(row):
        run_id, qid, ans, stored = row[:4]
        if not hasattr(tls, "c"):
            tls.c = NoMCP() if a.reuse_quotes else MCPClient(token)
        sent = strip_md(ans)
        stored_recon, stored_quotes = {}, None
        if a.reuse_check_brief:
            try:
                body = json.loads(stored or "")
            except (json.JSONDecodeError, TypeError):
                return row, None, "no stored check_brief body to reuse"
            old = body.pop("_citebench", None) or {}
            if not isinstance(body.get("cites"), list):
                return row, None, "stored check_brief body has no cites list"
            if old.get("sent_text") is not None and old["sent_text"] != sent:
                with lock:
                    counters["sent_text_changed"] += 1
            stored_recon = {rkey(ev.get("raw")): ev for ev in (old.get("reconciliation") or []) if ev.get("raw")}
            if a.reuse_quotes:
                if not str(old.get("grader_version") or "").startswith(("g7", "g8")) or "quote_results" not in old:
                    return row, None, "--reuse-quotes: stored grade has no g7+ quote verdicts"
                stored_quotes = old
        else:
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
            if rkey(c.get("raw")) in stored_recon:   # evidence raw may be spelled "504 Mich 152" for "504 Mich. 152"
                return stored_recon[rkey(c.get("raw"))]
            ck = (c.get("volume"), c.get("reporter"), c.get("page"), json.dumps(c.get("claimed")), qrow.get("state"))
            with lock:
                if ck in recon_cache:
                    return recon_cache[ck]
                if a.reuse_check_brief:
                    counters["recon_live"] += 1
            ev = reconcile(c, sent, qrow.get("state"), call_json)
            with lock:
                recon_cache[ck] = ev
            return ev

        try:
            if a.reuse_quotes:
                g, meta = summarize(sent, body, qrow or None, None, reconcile_fn, None, stored_quotes=stored_quotes)
            else:
                g, meta = summarize(sent, body, qrow or None, fetch_text, reconcile_fn, fetch_rule)
        except Exception as e:   # one bad row must not abort a 2,000-row regrade; it keeps its old grade
            return row, None, f"summarize failed: {type(e).__name__}: {e}"
        meta["sent_text"] = sent
        if a.reuse_check_brief:
            meta["check_brief_reused"] = True
        body["_citebench"] = meta
        old_counts = dict(zip([c.strip() for c in GRADE_COLS.split(",")], row[4:]))
        diff = {k: (old_counts[k], g[k]) for k in old_counts if k in g and old_counts[k] is not None and old_counts[k] != g[k]}
        if diff:
            meta["changed_from_stored"] = diff
        if a.dry_run:
            return row, (g, meta), None
        with lock:
            con.execute("INSERT OR REPLACE INTO grades (run_id, qid, n_cites, n_verified, n_fabricated, "
                        "n_unindexed, n_name_mismatch, n_quote_absent, n_quote_unattributed, n_red, n_yellow, gold_hit, "
                        "gold_equivalent, abstained, warned_treatment, grader_version, check_brief_json, n_pin_reference) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (run_id, qid, g["n_cites"], g["n_verified"], g["n_fabricated"], g["n_unindexed"],
                         g["n_name_mismatch"], g["n_quote_absent"], g["n_quote_unattributed"], g["n_red"],
                         g["n_yellow"], g["gold_hit"], g["gold_equivalent"], g["abstained"], g["warned_treatment"],
                         GRADER_VERSION, json.dumps(body), g["n_pin_reference"]))
            con.commit()
        return row, (g, meta), None

    with cf.ThreadPoolExecutor(max_workers=min(4, a.concurrency)) as ex:
        for row, res, err in ex.map(work, todo):
            run_id, qid = row[:2]
            if err:
                print(f"  {run_id} {qid}: GRADE ERROR {err}")
                continue
            g, meta = res
            extra = f" TRUNCATED {meta['truncated_bytes']}B" if meta["truncated_bytes"] else ""
            if meta.get("changed_from_stored"):
                counters["changed"] += 1
                extra += " CHANGED " + json.dumps(meta["changed_from_stored"], sort_keys=True)
            if meta.get("pin_reference") or meta.get("near_miss"):
                extra += " g8 pin=" + json.dumps([p["raw"] for p in meta["pin_reference"]]) + " near_miss=" + json.dumps(
                    [[n["raw"], n["kind"], n["cluster_id"], n["delta"]] for n in meta["near_miss"]])
            nogold = "" if meta["gold_found_in_question"] else " (no gold row found)"
            print(f"  {run_id} {qid}: cites={g['n_cites']} ver={g['n_verified']} fab={g['n_fabricated']} "
                  f"unidx={g['n_unindexed']} name_mm={g['n_name_mismatch']} quote_bad={g['n_quote_absent']} "
                  f"quote_unattr={g['n_quote_unattributed']} pin_ref={g['n_pin_reference']} red={g['n_red']} "
                  f"yel={g['n_yellow']} gold_hit={g['gold_hit']} gold_eq={g['gold_equivalent']} abstain={g['abstained']} "
                  f"warned={g['warned_treatment']}{extra}{nogold}", flush=True)
    print(f"{counters['changed']} rows' counts differ from their stored grade" + (" (dry run: nothing written)" if a.dry_run else ""))
    if a.reuse_check_brief:
        print(f"reuse mode: {counters['recon_live']} reconciliations not found in the stored evidence (run live, "
              f"no corpus DB); {counters['sent_text_changed']} rows whose stripped text differs from the stored one")

if __name__ == "__main__":
    main()
