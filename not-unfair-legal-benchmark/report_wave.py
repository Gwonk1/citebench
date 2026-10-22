# usage: python3 report_wave.py results/YYYYMMDD items/from_fixes.jsonl
# Reads saved CourtListener MCP bodies and says, per class, whether the trap fired.
import json
import os
import re
import sys

import score

HERE = os.path.dirname(os.path.abspath(__file__))


def load_items(path):
    rows = []
    with open(path) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def body(out, iid):
    p = os.path.join(out, iid + ".txt")
    if not os.path.exists(p):
        return None
    return open(p).read()


def trip(row, text):
    """Return (fired, detail). fired means CourtListener showed the weakness."""
    if text is None:
        return None, "missing"
    if text.startswith("ERROR"):
        return None, text[:180]
    klass = row["class"]
    if row.get("tool") == "cluster":
        fired = '"precedential_status": "Published"' in text or '"precedential_status":"Published"' in text
        return fired, "CL precedential_status Published" if fired else text[:160].replace("\n", " ")
    if row.get("tool") == "court":
        gold = row.get("gold") or {}
        wrong = gold.get("wrong", "")
        right = gold.get("right", "")
        m = re.search(r'"citation_string":\s*(null|"(?:\\.|[^"\\])*")', text)
        if not m:
            return None, "no citation_string in the court record"
        live = "" if m.group(1) == "null" else json.loads(m.group(1))
        fired = live == wrong and live != right
        return fired, f"live {live!r}  right {right!r}"
    if row.get("tool") == "opinion":
        tell = (row.get("gold") or {}).get("tell") or ""
        fired = text.startswith("snippet_found=True") or (tell and tell in text)
        return fired, "pre-fix garble still in the CourtListener opinion" if fired else "garble span not in the fetched opinion text"
    parsed = score.parse(text)
    cases = parsed["cases"]
    st = cases[0]["status"] if cases else ("NONE" if "No citations found" in text else "?")
    warn = bool(cases and cases[0]["warning"])
    other = cases[0]["other_cluster_ids"] if cases else []
    real = row["gold"].get("real_cite") or ""
    if klass == "coverage":
        return st == "NOT FOUND", st
    if klass == "wrong_index":
        return st == "FOUND", st + (" name-warning" if warn else "")
    if klass == "twin":
        fired = not other and st == "FOUND"
        detail = st + (f" other={other}" if other else " no other cluster named")
        return fired, detail
    if klass == "treatment" and row["id"].startswith("c4-"):
        return st == "FOUND" and "overrul" not in text.lower() and "reced" not in text.lower(), st
    if klass == "treatment":
        return st == "FOUND" and "unpublish" not in text.lower(), st
    if klass == "pagination":
        named = real and real in text
        return st == "NOT FOUND" and not named, st + ("" if not named else " named the real cite")
    if klass == "vendor":
        return st in ("NOT FOUND", "NONE", "?"), st
    if klass == "misprint":
        named = real and real in text
        return st == "NOT FOUND" and not named, st + ("" if not named else " named the real cite")
    if klass == "caption":
        return (st == "NOT FOUND") or warn, st + (" name-warning" if warn else "")
    if klass == "opinion_cite":
        return st == "NOT FOUND", st
    if klass == "bluebook_court":
        generic = "/courts/fladistctapp/" in text or "Fla. Dist. Ct. App." in text
        want = row["gold"].get("parenthetical") or ""
        named = want and want in text
        return generic and not named, ("generic Fla. Dist. Ct. App." if generic else "court not generic") + (f"; wanted {want}" if want else "")
    if klass == "vendor_when_official":
        offered = (" WL " in (" " + text)) or ("LEXIS" in text)
        return offered, "lists WL or LEXIS beside the reporter" if offered else "reporter only"
    return None, st


def main():
    out = sys.argv[1]
    items = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "items", "from_fixes.jsonl")
    rows = load_items(items)
    by = {}
    for row in rows:
        fired, detail = trip(row, body(out, row["id"]))
        by.setdefault(row["class"], []).append((row["id"], fired, detail))
        mark = {True: "TRIP", False: "held", None: "????"}[fired]
        print(f"{mark:4} {row['id']:16} {detail}")
    print()
    for klass, recs in by.items():
        n = len(recs)
        t = sum(1 for _, f, _ in recs if f is True)
        h = sum(1 for _, f, _ in recs if f is False)
        q = n - t - h
        print(f"{klass:14} trip {t:3}  held {h:3}  other {q:3}  of {n}")


if __name__ == "__main__":
    main()
