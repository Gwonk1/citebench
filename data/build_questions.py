#!/usr/bin/env python3
# usage: python3 data/build_questions.py [--seed 20260922] [--out data/questions.jsonl] [--audit N]
"""Build the citebench question set (data/questions.jsonl, schema in SCHEMA.md).

Pipeline (all source DBs opened read-only via ?mode=ro URIs):
  1. target_propositions_slim.db  -> candidate propositions (citation_count >= MIN_CITES),
     text-quality filters, best surviving proposition per gold cluster.
  2. caselaw_meta.db (cases/citations/courts, indexed by cluster_id) -> court, name,
     date, reporter citations. Published opinions with a real reporter cite only.
  3. court_state.db -> state / federal classification of the gold court.
  4. syfertize_deploy.db treatment_summary -> gold_flag (the live serving flag).
  5. Stratified, seeded sampling (~10% yellow/red gold cases per stratum on purpose).
  6. Bluebook cite rendered by the production lib (/var/www/lib/bluebook.php, read
     only, via `php`) so gold_citation matches what syfert.com shows.

No COUNT(*); the only full scan is the ~300 MB propositions table.
"""
import argparse
import json
import random
import re
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict

PROPS_DB = "/mnt/crucial/syfertize/target_propositions_slim.db"
META_DB = "/mnt/caselaw/pkg/caselaw_meta.db"
COURT_STATE_DB = "/mnt/crucial/syfertize/cache/court_state.db"
DEPLOY_DB = "/mnt/crucial/syfertize/syfertize_deploy.db"
BLUEBOOK_LIB = "/var/www/lib/bluebook.php"
FL_DCA_DB = "/var/www/caselaw/cache/fl_dca_districts.db"   # same lookup case.php uses

MIN_CITES = 5          # floor for the candidate scan; ranking prefers higher counts
MIN_CITES_BAD = 2      # red/yellow clusters are rare (~6.6k corpus-wide): lower floor for them
MIN_WORDS, MAX_WORDS = 12, 60

# Hand-review rejections (target_propositions rowids). Filled from the eyeball passes documented
# in data/README.md; skipped at draw time (like a near-duplicate) so the rest of the seeded draw
# is unchanged.
MANUAL_REJECT = {
    682612,   # Allstate v. Ruiz: "there simply is no basis ... claim file type material" (context)
    1250967,  # Commonwealth v. Flowers: imperative fragment "conduct an independent review ..."
    707021,   # Baptist Hosp. v. Maler: condition clause, not a rule
    1365119,  # In re Schaefer: "pursuant to the statute" (context-dependent)
    # full-set pass
    1075845,  # People v. Banks: "no one of these considerations ..." (context)
    624578,   # Perera: dangling "where ... would do so."
    647934,   # Capital Bank v. MVB: half of a fiduciary-duty definition
    659200,   # Johnson v. State (3d DCA): "nothing in melbourne ..." (depends on another case)
    691013,   # Griffin v. State: "it is a relevant and inseparable part ..." (pronoun + splice)
    861750,   # Raunela v. Hertz: "anywhere in the evidence ..." (fragment)
    866932,   # Brookline v. Goldstein: "... also may be considered" (context)
    606497,   # Malik v. State: subjectless list "sets out the law, ..."
    46388,    # United States v. Bagley: bare "if there is a reasonable probability ..." clause
    4869,     # Byers v. Dallas Morning News: imperative "respond to the motion ..."
    575071,   # People v. Watson: bare "it is reasonably probable that ..." standard clause
    1104943,  # People v. Clark: same "no one of these considerations" sentence as Banks
    10129,    # Delta & Pine Land: bare Anderson clause "a reasonable jury could not return ..."
    647736,   # Advisory Op. Re Tax: subjectless "electorate is advised ..."
    616289,   # Figueroa: stray-quote splice "substantial evidence' means 'such ..."
    1272875,  # Jacobsen: "burden is a heavy one" (antecedent missing)
    148394,   # Carroll v. Sec'y HHS: "the burden then shifts ..." (context)
    392,      # Santiago v. Walls: fact-bound condition, not a rule
    384373,   # Fid. & Cas. v. Cope: "no such action may be maintained" (context)
    329259,   # Dole v. Chandler: consequence clause lifted from an "otherwise, ..." sentence
}
BAD_SHARE = 0.10       # deliberate yellow/red gold cases per stratum

# ---- strata -------------------------------------------------------------------
# (stratum key, n). Florida = state courts only (fla + DCAs). Federal = F/FD courts.
OTHER_STATES = ["ny", "ca", "tx", "ga", "il", "pa", "oh", "nj", "ma", "mi"]
STRATA = [("fl", 150), ("us:scotus", 20), ("us:circuit", 30), ("us:district", 10)] + \
         [(f"st:{s}", 9) for s in OTHER_STATES]

STATE_NAMES = {"fl": "Florida", "ny": "New York", "ca": "California", "tx": "Texas",
               "ga": "Georgia", "il": "Illinois", "pa": "Pennsylvania", "oh": "Ohio",
               "nj": "New Jersey", "ma": "Massachusetts", "mi": "Michigan"}
CIRCUIT_NAMES = {"ca1": "First", "ca2": "Second", "ca3": "Third", "ca4": "Fourth",
                 "ca5": "Fifth", "ca6": "Sixth", "ca7": "Seventh", "ca8": "Eighth",
                 "ca9": "Ninth", "ca10": "Tenth", "ca11": "Eleventh"}
STATE_TO_CIRCUIT = {
    **{s: "ca1" for s in ["me", "ma", "nh", "ri", "pr"]},
    **{s: "ca2" for s in ["ct", "ny", "vt"]},
    **{s: "ca3" for s in ["de", "nj", "pa", "vi"]},
    **{s: "ca4" for s in ["md", "nc", "sc", "va", "wv"]},
    **{s: "ca5" for s in ["la", "ms", "tx"]},
    **{s: "ca6" for s in ["ky", "mi", "oh", "tn"]},
    **{s: "ca7" for s in ["il", "in", "wi"]},
    **{s: "ca8" for s in ["ar", "ia", "mn", "mo", "ne", "nd", "sd"]},
    **{s: "ca9" for s in ["ak", "az", "ca", "hi", "id", "mt", "nv", "or", "wa", "gu"]},
    **{s: "ca10" for s in ["co", "ks", "nm", "ok", "ut", "wy"]},
    **{s: "ca11" for s in ["al", "fl", "ga"]},
}

# ---- text-quality filters -----------------------------------------------------
BAD_START = set("""that which who whom whose and or but nor because whether to as than of so
since although though until while being having with without for by from into on at is are
was were be been not also then thus therefore however id see cf accord quoting citing internal
he she they its their his her this these those we our us i such said here must may can
cannot should shall will would could might do does did has have had even only""".split())
NOUNLESS_START = set("""one often almost enough award submit well-recognized
well well-settled well-established merely simply solely ends consists creates conclusive assure
first second third fourth finally then particular every accept marshal determine consider
construe view examine apply review decide assess weigh balance grant deny show prove establish
demonstrate identify conduct crucial necessary essential sufficient insufficient relevant appropriate
entitled subject liable free able unable proper improper unlikely likely goes""".split())
# "provides a mechanism", "assumes the role", "goes to the foundation": subjectless verb phrase
VERB_OBJECT_START = re.compile(
    r"^[a-z]+s (the|a|an|to|that|its|his|her|their|no|only|what|whether|for|from|with|into|on)\b")
# quoting enacted text (statute / rule / constitution): the controlling authority is the
# enactment, not the gold case
ENACTED_TEXT = re.compile(r"\bshall\b")
DEMONSTRATIVE = re.compile(
    r"\b(this|these|those|such|said|that)\s+(section|subsection|factors?|doctrine|determination|"
    r"rule|statute|test|standard|provision|chapter|act|opinion|analysis|inquiry|issue|claim|burden|"
    r"prong|step|exception|requirement|case|matter|order)\b|\bthe (latter|former)\b|\bin particular\b|\b(these|those) (considerations|factors|elements|"
    r"circumstances|requirements|principles|cases|facts|criteria|rules|standards|claims|issues)\b")
# the harvester often cuts the *condition* out of a harmless-error / Strickland sentence
# ("there is no reasonable possibility that ...") -- a clause, not a rule.
CONDITION_FRAGMENT = re.compile(
    r"^there (is|exists|has been|was) (a|no|more than)\b.*\b(reasonable (possibility|probability|"
    r"likelihood)|metaphysical doubt|violation of a clearly|fair probability)")
OCR_LINENO = re.compile(r"([a-z]+),? (\d{1,2}) [a-z]")
QTY_WORDS = set("""within of than to least section rule title chapter under the and or for after
before over about some only last first next all any at by in from with""".split())
LEGAL_WHITELIST = set("""alj aljs pcra ifp hac strickland anders roper miranda brady certiorari
nonmoving nonmovant movant movants appellate postconviction nonfrivolous unpreserved
preponderance scintilla mens rea actus reus res judicata estoppel quantum meruit pari materia
voir dire nunc pro tunc habeas corpus mandamus arguendo sua sponte bivens daubert frye batson
colloquy justiciable justiciability tortious tortfeasor tortfeasors indemnitor indemnitee
nonstatutory peremptories peremptory mitigator aggravator aggravators caselaw
ssa ssi dib erisa rico adea ada fmla flsa titlevii nlra aedpa pslra cafa pra tcpa fdcpa fcra
ineffectiveness unappealable nonfinal nonjury subsection subsections nondelegable""".split())
try:
    DICT = {w.strip().lower() for w in open("/usr/share/dict/words", encoding="utf-8", errors="ignore")}
except OSError:
    DICT = None


def non_dict_tokens(t):
    if DICT is None:
        return set()
    out = set()
    for w in re.findall(r"[a-z]{3,}", t.lower()):
        if w in DICT or w in LEGAL_WHITELIST:
            continue
        stems = [w[:-1], w[:-2], w[:-3], w[:-2] + "e" if w.endswith("ed") else w]
        if any(x in DICT for x in stems if x):
            continue
        out.add(w)
    return out
RELATIVE = re.compile(r"\b(that|which|who|whom|whose|what|whether)\b")
CONDITIONAL_START = {"where", "when", "if", "once", "after", "before", "unless", "absent",
                     "because", "although", "while", "whenever", "wherever"}
FINITE_VERB = re.compile(
    r"\b(is|are|was|were|must|may|might|can|cannot|could|should|shall|will|would|does|do|did|"
    r"has|have|had|requires?|provides?|applies|apply|holds?|means|constitutes?|"
    r"includes?|permits?|prohibits?|allows?|bars?|precludes?|governs?|lies|exists?|"
    r"depends?|turns?|operates?|extends?|entitles?|renders?|confers?|arises?)\b")
REJECT_PATTERNS = [
    (re.compile(r"\b(we|our|us|i)\b"), "first_person"),
    (re.compile(r"\b(this court|the court below|instant|in this case|here,|appellants?|appellees?|"
                r"petitioners?'?s?|respondents?'?s?)\b"), "case_specific"),
    (re.compile(r"\b(supra|infra|ibid|id\.|footnote|fn\.|n\.\s*\d)"), "citation_junk"),
    (re.compile(r"\sv\.\s"), "embedded_case_cite"),
    (re.compile(r"\*\d|\*\*"), "star_paging"),
    (re.compile(r"\S {2,}\S"), "stripped_symbol"),   # e.g. "under  1500" where the § was lost
    (re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f�-]"), "junk_bytes"),
    (re.compile(r"(\w)\1{3,}|_{3,}|-{3,}"), "ocr_runs"),
]


def reject_reason(p):
    """Return None if the proposition is a usable self-contained statement of law."""
    t = p.strip()
    words = t.split()
    if not (MIN_WORDS <= len(words) <= MAX_WORDS):
        return "length"
    core = t.rstrip("'\"” ")
    if not core.endswith("."):
        return "no_terminal_period"
    if core.endswith("..") or core.endswith(". ."):
        return "trailing_ellipsis"
    if t[0] in "([.,;:-'\"" or t[0].isdigit():
        return "fragment_start"
    first = re.sub(r"[^a-z]", "", words[0].lower())
    if first in BAD_START or first in NOUNLESS_START or FINITE_VERB.fullmatch(first):
        return "fragment_start"
    if VERB_OBJECT_START.match(t.lower()) and first not in ("there", "this", "thus"):
        return "fragment_start"
    if ENACTED_TEXT.search(t.lower()):
        return "enacted_text_quote"
    if first == "it" and (len(words) < 2 or words[1].lower() not in ("is", "has", "was")):
        return "pronoun_start"
    low0 = t.lower()
    if DEMONSTRATIVE.search(low0):
        return "context_reference"
    if CONDITION_FRAGMENT.search(low0):
        return "condition_fragment"
    if any(m.group(1) not in QTY_WORDS for m in OCR_LINENO.finditer(low0)):
        return "ocr_line_numbers"
    if len(non_dict_tokens(t)) >= 2:
        return "proper_nouns_or_ocr"
    # adverb / participle / bare-verb openers ("often turns on", "aimed at", "necessarily
    # circumscribed") are subjectless fragments; "generally, ..." is fine.
    if (first.endswith(("ly", "ed", "ing")) and not words[0].endswith(",")
            and first not in ("only",)):
        return "fragment_start"
    if first in CONDITIONAL_START:
        if "," not in t:
            return "dangling_conditional"
        # the main clause after the last comma must itself carry a finite verb
        if not FINITE_VERB.search(t.lower().rsplit(",", 1)[1]):
            return "dangling_conditional"
    m = FINITE_VERB.search(t.lower())
    if not m:
        return "no_finite_verb"
    if first not in CONDITIONAL_START and RELATIVE.search(t.lower()[:m.start()]):
        # "documents incorporated ... of which a court may take", "presumption that the
        # legislature has": the only finite verb sits inside a relative clause
        return "relative_clause_fragment"
    low = t.lower()
    for rx, why in REJECT_PATTERNS:
        if rx.search(low if why not in ("junk_bytes", "stripped_symbol", "ocr_runs") else t):
            return why
    if t.count('"') % 2:
        return "unbalanced_quote"
    openers = len(re.findall(r"(?:^|[\s(\[])'(?=\w)", t))
    closers = len(re.findall(r"(?<=[\w.,;:!?)\]])'(?=[\s.,;:)\]]|$)", t))
    if openers > closers:
        return "unbalanced_quote"
    digits = sum(c.isdigit() for c in t)
    if digits > 0.08 * len(t):
        return "digit_heavy"
    if sum(ord(c) > 127 for c in t) > 3:
        return "non_ascii"
    return None


def norm_tokens(p):
    return set(w for w in re.findall(r"[a-z]+", p.lower()) if len(w) > 2)


def display_prop(p):
    p = p.strip()
    return p[0].upper() + p[1:]


# ---- prompts ------------------------------------------------------------------
TEMPLATES = [
    ("You are assisting {a_jur} {jur_adj} litigator. Cite the controlling authority for this proposition, "
     "with a pinpoint if you can: {prop} Give the case name, reporter citation, court and year. "
     "If you are not certain a citation is real, say so instead of guessing."),
    ("I'm drafting a brief in {forum}. I need a case that stands for the following proposition: "
     "\"{prop}\" What is the best authority? Please give the full citation (case name, reporter, "
     "court, year) and a pin cite if possible. If you are unsure whether a case exists or actually "
     "says this, tell me rather than guess."),
    ("Research question ({jur_short}): what case should I cite for the following statement of law? "
     "\"{prop}\" Provide the case name, reporter citation, court, and year, with a pinpoint page if "
     "you know it. Do not invent citations; flag anything you are not sure about."),
    ("Opposing counsel's motion in {forum} asserts, without citing anything, that \"{prop}\" What is "
     "the leading authority for that proposition? Give the case name, reporter citation, court, year, "
     "and a pinpoint if you can. If you cannot confirm a real citation, say so."),
    ("Please find me {jur_adj} authority supporting this proposition for a memo: \"{prop}\" I need the "
     "case name, full reporter citation, deciding court, and year (pinpoint if available). Only cite "
     "cases you are confident actually exist; otherwise say you are not certain."),
]


def jurisdiction_phrases(stratum, court_id, court_state_code):
    if stratum == "fl":
        return {"jur_adj": "Florida", "forum": "a Florida state court",
                "jur_short": "Florida law"}
    if stratum.startswith("st:"):
        name = STATE_NAMES[stratum[3:]]
        art = "an" if name[0] in "AEIOU" else "a"
        return {"jur_adj": name, "forum": f"{art} {name} state court", "jur_short": f"{name} law",
                "a_jur": art}
    if stratum == "us:scotus":
        return {"jur_adj": "federal", "forum": "federal court", "jur_short": "federal law"}
    circ = court_id if stratum == "us:circuit" else STATE_TO_CIRCUIT.get(court_state_code or "")
    if circ in CIRCUIT_NAMES:
        c = CIRCUIT_NAMES[circ]
        return {"jur_adj": f"federal ({c} Circuit)", "forum": f"federal court in the {c} Circuit",
                "jur_short": f"federal law, {c} Circuit"}
    if circ == "cadc" or court_id in ("cadc", "dcd"):
        return {"jur_adj": "federal (D.C. Circuit)", "forum": "federal court in the D.C. Circuit",
                "jur_short": "federal law, D.C. Circuit"}
    return {"jur_adj": "federal", "forum": "federal court", "jur_short": "federal law"}


# courts.citation_string values that are not Bluebook (see README "known limitations"); the
# production lib passes them through unchanged, so fix them here for the gold string only.
COURT_ABBREV_FIX = {"M.D. Penn.": "M.D. Pa.", "E.D. Penn.": "E.D. Pa.", "W.D. Penn.": "W.D. Pa.",
                    "E.D.N.Y ": "E.D.N.Y. ", "S.D.N.Y ": "S.D.N.Y. ", "N.D.N.Y ": "N.D.N.Y. ",
                    "W.D.N.Y ": "W.D.N.Y. ", "S.D.W. Va ": "S.D. W. Va. ", "N.D.W. Va ": "N.D. W. Va. "}


def fix_court_abbrev(cite):
    for a, b in COURT_ABBREV_FIX.items():
        cite = cite.replace("(" + a, "(" + b)
    return cite


GENERIC_NAME_WORDS = set("""state states people united commonwealth city county town township
village department dept board florida insurance company corp inc bank national american
estate matter adoption welfare re parte the and of in for v""".split()) | set(
    n.lower() for n in STATE_NAMES.values())


def name_sane(name, date_filed):
    """Reject CL case names that are not a usable caption."""
    if not name or name == "Unknown" or len(name) > 80:
        return False
    if re.search(r"\b(appellants?|appellees?|plaintiffs?-|defendants?-|petitioners?-|No\.|No,)|"
                 r"^\d|\bv\. \.|SC\d\d|[A-Z]{4,}|\(\d|f/k/a|a/k/a|\(In Re|Slip Op|Appeal of|: ", name):
        return False
    if " v. " not in name and not re.match(r"(In re|Ex parte|Matter of|Adoption of|Care & Prot|"
                                           r"Est\. of|Advisory Op|In Re|Commonwealth|State)", name):
        return False
    yrs = [int(y) for y in re.findall(r"\b(1[89]\d\d|20\d\d)\b", name)]
    if date_filed and any(y > int(date_filed[:4]) for y in yrs):
        return False   # e.g. "Commonwealth v. One 1987 Mercury Cougar, 365 Mass. 747 (1974)"
    return True


def party_in_prop(name, prop):
    toks = {w for w in re.findall(r"[a-z]{4,}", name.lower()) if w not in GENERIC_NAME_WORDS}
    return bool(toks & set(re.findall(r"[a-z]{4,}", prop.lower())))


def render_bluebook(items, dca):
    """Render gold cites with the production lib (read-only include), one php process."""
    php_in = []
    for st, r, case, flag in items:
        m = re.match(r"fladistctapp(\d)$", case["court_id"])
        d = int(m.group(1)) if m else dca.get(case["cluster_id"])
        php_in.append({"case": case, "dca": d})
    php_code = (
        "require '" + BLUEBOOK_LIB + "';"
        "$in = json_decode(stream_get_contents(STDIN), true); $out = [];"
        "foreach ($in as $x) { $out[] = ['cite' => buildBluebookCite($x['case'], $x['dca']),"
        " 'name' => bluebookCaseName(best_case_name($x['case'], 'Unknown'))]; }"
        "echo json_encode($out);")
    res = subprocess.run(["php", "-r", php_code], input=json.dumps(php_in), capture_output=True,
                         text=True, check=True)
    return json.loads(res.stdout)


def ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def chunks(xs, n=500):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260922)
    ap.add_argument("--out", default="data/questions.jsonl")
    ap.add_argument("--audit", type=int, default=0, help="print N random candidates + verdicts")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    # 1. propositions ----------------------------------------------------------
    con = ro(PROPS_DB)
    rows = con.execute(
        "SELECT rowid, cluster_id, rank, proposition, citation_count, distinct_citers, "
        "distinct_courts, target_pin_page FROM target_propositions "
        "WHERE citation_count >= ? AND length(proposition) BETWEEN 50 AND 500", (MIN_CITES,)
    ).fetchall()
    # red/yellow gold cases are scarce, so pull their propositions separately at a lower floor
    dep = ro(DEPLOY_DB)
    bad_ids = [r[0] for r in dep.execute(
        "SELECT cluster_id FROM treatment_summary WHERE flag_color IN ('red','yellow')")]
    dep.close()
    seen = {r[0] for r in rows}
    for ch in chunks(bad_ids):
        q = ",".join("?" * len(ch))
        for r in con.execute(
                "SELECT rowid, cluster_id, rank, proposition, citation_count, distinct_citers, "
                f"distinct_courts, target_pin_page FROM target_propositions WHERE cluster_id IN ({q}) "
                "AND citation_count >= ? AND length(proposition) BETWEEN 50 AND 500",
                ch + [MIN_CITES_BAD]):
            if r[0] not in seen:
                rows.append(r)
    con.close()
    reasons = Counter()
    best = {}
    for r in rows:
        why = reject_reason(r[3])
        reasons[why or "ok"] += 1
        if why:
            continue
        key = (r[4], r[5], -r[2])
        if r[1] not in best or key > best[r[1]][0]:
            best[r[1]] = (key, r)
    print(f"[props] scanned {len(rows)} rows (cites>={MIN_CITES}); filter verdicts: "
          f"{dict(reasons.most_common())}", file=sys.stderr)
    print(f"[props] {len(best)} clusters with a usable proposition", file=sys.stderr)
    if args.audit:
        for r in rng.sample(rows, args.audit):
            print(f"  AUDIT {reject_reason(r[3]) or 'OK':>20} | {r[3]}", file=sys.stderr)

    cands = sorted((v[1] for v in best.values()), key=lambda r: (-r[4], r[1]))

    # 2. case metadata ---------------------------------------------------------
    cs = ro(COURT_STATE_DB)
    court_state = {r[0]: r for r in cs.execute(
        "SELECT court_id, state, is_federal, level, jurisdiction, citation_string FROM court_state")}
    cs.close()
    meta = ro(META_DB)
    court_cite = dict(meta.execute("SELECT id, citation_string FROM courts"))
    cases = {}
    for ch in chunks([r[1] for r in cands]):
        q = ",".join("?" * len(ch))
        for c in meta.execute(
                f"SELECT cluster_id, court_id, case_name, case_name_short, case_name_full, "
                f"date_filed, docket_number, precedential_status FROM cases "
                f"WHERE cluster_id IN ({q})", ch):
            cases[c[0]] = {"cluster_id": c[0], "court_id": c[1] or "", "case_name": c[2],
                           "case_name_short": c[3], "case_name_full": c[4], "date_filed": c[5],
                           "docket_number": c[6] or "", "precedential_status": c[7],
                           "court_citation_string": court_cite.get(c[1], ""), "citations": []}
        for c in meta.execute(
                f"SELECT cluster_id, volume, reporter, page, type FROM citations "
                f"WHERE cluster_id IN ({q}) ORDER BY cluster_id, id", ch):
            if c[0] in cases:
                cases[c[0]]["citations"].append(
                    {"volume": c[1], "reporter": c[2], "page": c[3], "type": c[4]})
    meta.close()

    # 3. flags -----------------------------------------------------------------
    dep = ro(DEPLOY_DB)
    flags = {}
    for ch in chunks(list(cases)):
        q = ",".join("?" * len(ch))
        flags.update(dep.execute(
            f"SELECT cluster_id, flag_color FROM treatment_summary WHERE cluster_id IN ({q})", ch))
    dep.close()

    # 4. stratum assignment ----------------------------------------------------
    def stratum_of(case):
        cs_row = court_state.get(case["court_id"])
        if not cs_row:
            return None
        _, st, fed, level, juris, _ = cs_row
        if fed:
            if case["court_id"] == "scotus":
                return "us:scotus"
            if juris == "F" and case["court_id"] in CIRCUIT_NAMES or case["court_id"] in ("cadc",):
                return "us:circuit"
            if juris == "FD":
                return "us:district"
            return None
        if juris not in ("S", "SA"):
            return None
        if st == "fl":
            return "fl"
        if st in OTHER_STATES:
            return f"st:{st}"
        return None

    US_ANCHORS = [(1900, 176), (1950, 338), (1970, 397), (1980, 444), (1990, 494),
                  (2000, 528), (2010, 559), (2020, 589), (2030, 620)]

    def expected_us_volume(year):
        for (y0, v0), (y1, v1) in zip(US_ANCHORS, US_ANCHORS[1:]):
            if y0 <= year <= y1:
                return v0 + (v1 - v0) * (year - y0) / (y1 - y0)
        return None

    REPORTER_OK = {
        "fl": r"^So\. ?(2d|3d)?$",
        "us:circuit": r"^F\. ?(2d|3d|4th)?$",
        "us:district": r"^F\. ?Supp\.",
        # regional reporters only: CL's official-reporter-only rows are where most of the
        # wrong-volume errors live (505 Mich. for a 1999 case, 168 N.J. on an App. Div. case)
        "st:ny": r"^(N\.E\.|N\.Y\.S\.)", "st:ca": r"^P\.",
        "st:tx": r"^S\.W\.", "st:ga": r"^S\.E\.", "st:il": r"^N\.E\.",
        "st:pa": r"^A\.", "st:oh": r"^N\.E\.", "st:nj": r"^A\.",
        "st:ma": r"^N\.E\.", "st:mi": r"^N\.W\.",
    }

    def cite_sane(st, case, cite):
        """Guard against CL metadata errors (an FL case carrying an S.W.3d cite, a 2003
        SCOTUS case carrying 587 U.S.): the rendered primary cite must fit the court."""
        m = re.search(r", (\d+) (.+?) (\d+) \(", cite)
        if not m:
            return False
        vol, rep = int(m.group(1)), m.group(2)
        if st == "us:scotus":
            if rep != "U.S.":
                return False
            ev = expected_us_volume(int(case["date_filed"][:4]))
            return ev is not None and abs(vol - ev) <= 8
        rx = REPORTER_OK.get(st)
        if rx and not re.match(rx, rep):
            return False
        if st == "st:mi" and case["court_id"] == "michctapp" and rep.startswith("Mich.") \
                and not rep.startswith("Mich. App."):
            return False
        if case["court_id"] == "calctapp" and rep.startswith("P.") and \
                int((case["date_filed"] or "0")[:4]) > 1960:
            return False   # P.2d/P.3d after 1960 = Cal. Supreme Court; CL court id is wrong
        if st == "fl" and case["court_id"].startswith("fladistctapp") and "DCA" not in cite:
            return False   # district unresolvable -> not a proper Bluebook FL DCA cite
        return True

    def real_cite(case):
        for c in case["citations"]:
            rep = (c["reporter"] or "").lower()
            if c["type"] in (6, 7) or "lexis" in rep or rep == "wl":
                continue
            return True
        return False

    dca = {}
    fld = ro(FL_DCA_DB)
    fl_ids = [cid for cid, c in cases.items() if c["court_id"].startswith("fladistctapp")]
    for ch in chunks(fl_ids):
        q = ",".join("?" * len(ch))
        dca.update(fld.execute(
            f"SELECT cluster_id, district FROM fl_dca_districts WHERE cluster_id IN ({q})", ch))
    fld.close()

    pre = []
    skipped = Counter()
    for r in cands:
        case = cases.get(r[1])
        if not case:
            skipped["no_case_row"] += 1
            continue
        if case["precedential_status"] != "Published":
            skipped["unpublished"] += 1
            continue
        if not real_cite(case):
            skipped["no_reporter_cite"] += 1
            continue
        if not (case["case_name"] or case["case_name_short"] or case["case_name_full"]):
            skipped["no_case_name"] += 1
            continue
        flag = flags.get(r[1])
        if flag not in ("green", "yellow", "red"):
            skipped[f"flag_{flag}"] += 1
            continue
        st = stratum_of(case)
        if not st:
            skipped["out_of_strata"] += 1
            continue
        pre.append((st, r, case, flag))

    rendered = render_bluebook(pre, dca)
    for rd in rendered:
        rd["cite"] = fix_court_abbrev(rd["cite"])

    # reporter volume <-> year consistency, learned from the candidate pool itself: a cite
    # whose year is >3 years off the median of neighbouring volumes of the same reporter is a
    # CL metadata error (e.g. "Lugo v. Ameritech, 512 Mich. 95 (2001)"; real cite 464 Mich. 512)
    vol_years = defaultdict(list)
    parsed = []
    for (st, r, case, flag), rd in zip(pre, rendered):
        m = re.search(r", (\d+) (.+?) (\d+) \(.*?(\d{4})\)\.$", rd["cite"])
        parsed.append(m)
        if m:
            vol_years[m.group(2)].append((int(m.group(1)), int(m.group(4))))
    for k in vol_years:
        vol_years[k].sort()

    def vol_year_ok(m):
        rep, vol, yr = m.group(2), int(m.group(1)), int(m.group(4))
        near = [y for v, y in vol_years[rep] if abs(v - vol) <= 3]
        if len(near) < 5:
            return True          # too little evidence either way
        near.sort()
        return abs(near[len(near) // 2] - yr) <= 3

    pools = defaultdict(lambda: {"good": [], "bad": []})
    for (st, r, case, flag), rd, m in zip(pre, rendered, parsed):
        if not cite_sane(st, case, rd["cite"]):
            skipped["cite_sanity"] += 1
            continue
        if not m or not vol_year_ok(m):
            skipped["vol_year_mismatch"] += 1
            continue
        if not name_sane(rd["name"], case["date_filed"]):
            skipped["bad_case_name"] += 1
            continue
        if party_in_prop(rd["name"], r[3]):
            skipped["party_name_in_prop"] += 1
            continue
        pools[st]["good" if flag == "green" else "bad"].append((r, case, flag, rd))
    print(f"[meta] skipped: {dict(skipped)}", file=sys.stderr)
    for st, _ in STRATA:
        print(f"[pool] {st:12s} green={len(pools[st]['good'])} "
              f"yellow/red={len(pools[st]['bad'])}", file=sys.stderr)

    # 5. sampling --------------------------------------------------------------
    chosen, chosen_tokens = [], []

    def near_dup(p):
        t = norm_tokens(p)
        for u in chosen_tokens:
            if len(t & u) / max(1, len(t | u)) >= 0.5:
                return True
        return False

    def draw(pool, n, pool_mult=4):
        # pool is sorted by citation_count desc: sample from the top n*pool_mult (well-cited),
        # widening if near-dups exhaust it.
        picked = []
        width = n * pool_mult
        tried = set()
        while len(picked) < n:
            window = [x for x in pool[:width] if x[0][0] not in tried]
            if not window and width >= len(pool):
                break
            rng.shuffle(window)
            for x in window:
                tried.add(x[0][0])
                if len(picked) >= n:
                    break
                if x[0][0] in MANUAL_REJECT or near_dup(x[0][3]):
                    continue
                picked.append(x)
                chosen_tokens.append(norm_tokens(x[0][3]))
            width *= 2
        return picked

    for st, n in STRATA:
        n_bad = round(n * BAD_SHARE)
        bad = draw(pools[st]["bad"], n_bad, pool_mult=3)
        good = draw(pools[st]["good"], n - len(bad))
        if len(bad) + len(good) < n:
            print(f"[warn] {st}: only {len(bad) + len(good)}/{n}", file=sys.stderr)
        for x in bad + good:
            chosen.append((st,) + x)

    # 7. emit ------------------------------------------------------------------
    order = list(range(len(chosen)))
    rng.shuffle(order)
    with open(args.out, "w") as f:
        for i, idx in enumerate(order, 1):
            st, r, case, flag, rd = chosen[idx]
            cs_row = court_state.get(case["court_id"])
            ph = jurisdiction_phrases(st, case["court_id"], cs_row[1] if cs_row else None)
            tmpl = TEMPLATES[rng.randrange(len(TEMPLATES))]
            prop = display_prop(r[3])
            ph.setdefault("a_jur", "a")
            rec = {
                "id": f"q{i:04d}",
                "state": "us" if st.startswith("us:") else ("fl" if st == "fl" else st[3:]),
                "court": case["court_id"],
                "proposition": r[3],
                "prompt": tmpl.format(prop=prop, **ph),
                "gold_cluster_id": r[1],
                "gold_citation": rd["cite"],
                "gold_case_name": rd["name"],
                "gold_decision_date": case["date_filed"],
                "gold_flag": flag,
                "source_row": r[0],
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tally = Counter((c[0], c[3]) for c in chosen)
    print(f"[done] wrote {len(chosen)} questions to {args.out}", file=sys.stderr)
    for st, n in STRATA:
        print(f"  {st:12s} target={n:3d} got={sum(v for (s, _), v in tally.items() if s == st):3d} "
              f"green={tally[(st, 'green')]} yellow={tally[(st, 'yellow')]} red={tally[(st, 'red')]}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
