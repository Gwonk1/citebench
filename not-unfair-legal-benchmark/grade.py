# Grade one answer text against one task. The answer can come from any model or MCP.
#
# v1.1 (2026-10-25). The PROMPT asks for a final line that begins "ANSWER:".
# right / any_right / any_of are read over the whole answer. wrong, absent and
# forbid_vendor are read on the ANSWER line only, so an answer may name the bad
# form while explaining the correction ("Fla. 1st DCA, not Fla. Dist. Ct. App.").
# A treatment verdict (gold.verdict_line) must appear on the ANSWER line and may
# not be negated ("has not been overruled" is not "overruled"). When there is no
# ANSWER line the last non-empty line is graded instead and the per-item result
# carries no_answer_line = True.
import re
import unicodedata

PROMPT = """You are checking a legal citation or a court name.

Reply with the Bluebook form. Use the corrected court abbreviation.
If the citation does not exist, say that it does not exist.
If the citation is correct as written, say so and repeat it.
If the printed page is not the first page of the case, give the first page.
If two cases share the citation, name both.
If the case has been overruled, receded from, or abrogated, say so.
If the opinion is unpublished or nonprecedential, say so. If it was later ordered published, give the published reporter citation as the current citation.
If a quotation is garbled or not safe to quote, say so.
Do not use a Westlaw or LEXIS citation when a reporter citation exists.
If the citation is a denial of certiorari, an orders page, or a dismissal for want of a substantial federal question, say so. If that citation is not the decision's own reporter citation, give the reporter citation.
If the case name does not match the citation, say so.
If the reporter in the passage is the wrong series, give the reporter the decision is actually in.
For a Florida district court of appeal, use the form the Florida courts prescribe in Fla. R. App. P. 9.800: Fla. 1st DCA, Fla. 2d DCA, Fla. 3d DCA, Fla. 4th DCA, Fla. 5th DCA, Fla. 6th DCA. Do not write Fla. Dist. Ct. App.
End with one line that begins "ANSWER:" and holds only your corrected citation, court abbreviation, case name, or verdict (for example "overruled by ...", "unpublished", "cert. denied", "correct as written", "does not exist"). Do not repeat the wrong form on that line.
"""

REJECT = (
    "not found",
    "does not exist",
    "doesn't exist",
    "do not exist",
    "no such case",
    "may be incorrect",
    "not a real case",
    "cannot find",
    "can't find",
    "could not find",
    "no case",
    "not this case",
    "does not match",
    "wrong case",
    "fabricated",
    "hallucinat",
    "not a section",
    "no such section",
    "no such title",
)

NEGATION = re.compile(
    r"\b(not|never|no|none|neither|nor|without|isn't|wasn't|hasn't|haven't|aren't|weren't|cannot|can't|un)\b"
)
_ANSWER_LINE = re.compile(r"^\W*answer\s*:\s*(.*)$", re.I)
_DASHES = re.compile("[‐‑‒–—―−]|--+")


def norm(s):
    """Casefold; one kind of apostrophe, one kind of dash, one space; no space around a dash."""
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("’", "'").replace("‘", "'").replace("`", "'").replace("ʼ", "'")
    s = s.replace(" ", " ")
    s = _DASHES.sub("-", s)
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", " ", s)
    return s.casefold().strip()


def render(task):
    return PROMPT + "\n" + (task.get("text") or "").strip() + "\n"


def answer_line(answer):
    """(line, found). The last line that begins ANSWER:, else the last non-empty line."""
    lines = [ln.strip() for ln in (answer or "").splitlines() if ln.strip()]
    for ln in reversed(lines):
        m = _ANSWER_LINE.match(ln)
        if m:
            body = m.group(1).strip()
            return (body or ln), True
    return (lines[-1] if lines else ""), False


def _vendor(text):
    return bool(re.search(r"\bwl\b", text)) or "lexis" in text or "westlaw" in text


def _positive_hit(text, phrase):
    """phrase occurs in text at least once without a negation in the same clause before it."""
    start = 0
    while True:
        i = text.find(phrase, start)
        if i < 0:
            return False
        window = text[max(0, i - 48):i]
        # Only the current clause: cut at the last sentence or clause break.
        cut = max(window.rfind(ch) for ch in ".;:!?\n")
        if cut >= 0:
            window = window[cut + 1:]
        if not NEGATION.search(window):
            return True
        start = i + len(phrase)


def grade_item(answer, gold):
    """Full result: passed, reason, no_answer_line, answer_line."""
    g = gold or {}
    full = norm(answer)
    line_raw, has_line = answer_line(answer)
    line = norm(line_raw)
    out = {"passed": False, "reason": "", "no_answer_line": not has_line, "answer_line": line_raw}

    def fail(why):
        out["reason"] = why
        return out

    def ok(why="ok"):
        out["passed"] = True
        out["reason"] = why
        return out

    rights = [norm(x) for x in (g.get("right") or []) if x]
    any_right = [norm(x) for x in (g.get("any_right") or []) if x]
    wrongs = [norm(x) for x in (g.get("wrong") or []) if x]
    any_of = [norm(x) for x in (g.get("any_of") or []) if x]
    absent = [norm(x) for x in (g.get("absent") or []) if x]

    if g.get("reject"):
        scope = line if has_line else full
        if any(p in scope for p in REJECT):
            return ok("rejected")
        return fail("did not reject the cite")

    # right: every string must appear somewhere. any_right: one alternative is enough.
    if rights:
        missing = next((r for r in rights if r not in full), None)
        if missing is not None:
            shown = (g.get("right") or [""])[rights.index(missing)]
            return fail("missing " + shown)
    matched = None
    if any_right:
        matched = next((r for r in any_right if r in full), None)
        if matched is None:
            return fail("missing " + " / ".join(g.get("any_right") or []))

    # any_of: a verdict word. On the ANSWER line for treatment items; never negated.
    if any_of:
        scope = line if g.get("verdict_line") else full
        if not any(_positive_hit(scope, p) for p in any_of):
            where = " on the ANSWER line" if g.get("verdict_line") else ""
            return fail("missing " + " / ".join(g.get("any_of") or []) + where)

    # absent, forbid_vendor, wrong: the ANSWER line only.
    hit = next((p for p in absent if p in line), None)
    if hit is not None:
        return fail("answer line says " + hit)

    if g.get("forbid_vendor") and _vendor(line):
        return fail("vendor cite on the answer line")

    held = list(rights)
    if matched:
        held.append(matched)
    if wrongs:
        rest = line
        for r in held:
            rest = rest.replace(r, "")
        for w in wrongs:
            if any(w in r for r in held):
                if w in rest:
                    return fail("answer line also has " + w)
            elif w in line:
                return fail("answer line has " + w)
    return ok()


def grade(answer, gold):
    """Return (passed, reason). See grade_item for the per-item flags."""
    r = grade_item(answer, gold)
    return r["passed"], r["reason"]


def _good_answer(g):
    bits = []
    if g.get("reject"):
        bits.append("This citation does not exist.")
    else:
        bits.extend(g.get("right") or [])
        if g.get("any_right"):
            bits.append(g["any_right"][0])
        if g.get("any_of"):
            bits.append(g["any_of"][0])
    return " ".join(bits) or "ok"


def self_check(task):
    """A hand-built right answer passes, and the known bad form fails."""
    g = task["gold"]
    good = _good_answer(g)
    passed, why = grade("Explanation.\nANSWER: " + good, g)
    if not passed:
        return False, "good answer failed: " + why + " :: " + good
    if g.get("reject"):
        bad_ok, _ = grade("ANSWER: Status: FOUND. This is a real case.", g)
        if bad_ok:
            return False, "a confirmation was accepted"
    if g.get("wrong"):
        bad = g["wrong"][0]
        # A wrong form that is only a prefix of the right form is not itself an answer.
        if bad and not any(bad in r for r in (g.get("right") or []) + (g.get("any_right") or [])):
            bad_ok, _ = grade("ANSWER: " + bad, g)
            if bad_ok:
                return False, "bad form was accepted: " + bad
            # The bad form in the explanation, the good one on the ANSWER line, passes.
            both_ok, why = grade(bad + " is wrong.\nANSWER: " + good, g)
            if not both_ok:
                return False, "bad form in the explanation was punished: " + why
    if g.get("absent"):
        base = _good_answer(g)
        bad_ok, _ = grade("ANSWER: " + base + " " + g["absent"][0], g)
        if bad_ok:
            return False, "a rejection of a real cite was accepted"
    if g.get("forbid_vendor"):
        base = _good_answer(g)
        bad_ok, _ = grade("ANSWER: " + base + " 2016 WL 1", g)
        if bad_ok:
            return False, "a vendor cite was accepted"
    if g.get("any_of") and not g.get("reject"):
        base = []
        base.extend(g.get("right") or [])
        if g.get("any_right"):
            base.append(g["any_right"][0])
        bad_ok, _ = grade("ANSWER: " + " ".join(base) + " Status: FOUND. The case is good law.", g)
        if bad_ok:
            return False, "silence on the required flag was accepted"
        neg_ok, _ = grade("ANSWER: " + " ".join(base) + " has not been " + g["any_of"][0], g)
        if neg_ok:
            return False, "a negated flag was accepted"
    return True, "ok"
