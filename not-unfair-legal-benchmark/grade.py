# Grade one answer text against one task. The answer can come from any model or MCP.
# A pass is the corrected string present in the answer. A vendor cite, a rejection of a
# real cite, or the uncorrected court form fails the item.
import re
import unicodedata

PROMPT = """You are checking a legal citation or a court name.

Reply with the Bluebook form. Use the corrected court abbreviation.
If the citation does not exist, say that it does not exist.
If the printed page is not the first page of the case, give the first page.
If two cases share the citation, name both.
If the case has been overruled, receded from, or abrogated, say so.
If the opinion is unpublished or nonprecedential, say so.
If a quotation is garbled or not safe to quote, say so.
Do not use a Westlaw or LEXIS citation when a reporter citation exists.
If the citation is a denial of certiorari, an orders page, or a dismissal for want of a substantial federal question, say so. If that citation is not the decision's own reporter citation, give the reporter citation.
If the case name does not match the citation, say so.
If the reporter in the passage is the wrong series, give the reporter the decision is actually in.
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
    "no case",
    "not this case",
    "does not match",
    "wrong case",
)


def norm(s):
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("`", "'")
    s = s.replace("\u00a0", " ")
    return s.casefold()


def render(task):
    return PROMPT + "\n" + (task.get("text") or "").strip() + "\n"


def _vendor(answer):
    return bool(re.search(r"\bwl\b", answer)) or "lexis" in answer or "westlaw" in answer


def grade(answer, gold):
    """Return (passed, reason). gold uses right, wrong, any_of, absent, reject, forbid_vendor."""
    a = norm(answer)
    g = gold or {}
    rights = [norm(x) for x in (g.get("right") or []) if x]
    any_right = [norm(x) for x in (g.get("any_right") or []) if x]
    wrongs = [norm(x) for x in (g.get("wrong") or []) if x]
    any_of = [norm(x) for x in (g.get("any_of") or []) if x]
    absent = [norm(x) for x in (g.get("absent") or []) if x]

    if g.get("reject"):
        if any(p in a for p in REJECT):
            return True, "rejected"
        return False, "did not reject the cite"

    # right: every string must appear. any_right: one alternative is enough.
    if rights:
        missing = next((r for r in rights if r not in a), None)
        if missing is not None:
            shown = (g.get("right") or [""])[rights.index(missing)]
            return False, "missing " + shown
    matched = None
    if any_right:
        matched = next((r for r in any_right if r in a), None)
        if matched is None:
            return False, "missing " + (g.get("any_right") or [""])[0]

    if any_of and not any(p in a for p in any_of):
        return False, "missing " + " / ".join(g.get("any_of") or [])

    if any(p in a for p in absent):
        hit = next(p for p in absent if p in a)
        return False, "answer says " + hit

    if g.get("forbid_vendor") and _vendor(a):
        return False, "vendor cite in the answer"

    held = list(rights)
    if matched:
        held.append(matched)
    if held and wrongs:
        rest = a
        for r in held:
            rest = rest.replace(r, "")
        for w in wrongs:
            if any(w in r for r in held):
                if w in rest:
                    return False, "also has " + w
            elif w in a:
                return False, "has " + w
    return True, "ok"


def self_check(task):
    """A hand-built right answer passes, and the known bad form fails."""
    g = task["gold"]
    good_bits = []
    if g.get("reject"):
        good_bits.append("This citation does not exist.")
    else:
        if g.get("right"):
            good_bits.extend(g["right"])
        if g.get("any_right"):
            good_bits.append(g["any_right"][0])
        if g.get("any_of"):
            good_bits.append(g["any_of"][0])
    good = " ".join(good_bits) or "ok"
    passed, why = grade(good, g)
    if not passed:
        return False, "good answer failed: " + why + " :: " + good
    if g.get("reject"):
        bad_ok, _ = grade("Status: FOUND. This is a real case.", g)
        if bad_ok:
            return False, "a confirmation was accepted"
    elif g.get("wrong"):
        bad = g["wrong"][0]
        # A wrong form that is only a prefix of the right form is not itself an answer.
        if bad and not any(bad in r for r in (g.get("right") or [])):
            bad_ok, _ = grade(bad, g)
            if bad_ok:
                return False, "bad form was accepted: " + bad
    elif g.get("absent"):
        base = (g.get("right") or g.get("any_right") or ["x"])[0]
        bad_ok, _ = grade(base + " " + g["absent"][0], g)
        if bad_ok:
            return False, "a rejection of a real cite was accepted"
    elif g.get("forbid_vendor"):
        base = ((g.get("right") or g.get("any_right") or ["x"])[0])
        bad_ok, _ = grade(base + " 2016 WL 1", g)
        if bad_ok:
            return False, "a vendor cite was accepted"
    elif g.get("any_of"):
        base = []
        if g.get("right"):
            base.extend(g["right"])
        if g.get("any_right"):
            base.append(g["any_right"][0])
        bad_ok, _ = grade(" ".join(base) + " Status: FOUND. The case is good law.", g)
        if bad_ok:
            return False, "silence on the required flag was accepted"
    return True, "ok"
