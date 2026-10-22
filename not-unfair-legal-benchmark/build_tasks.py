# Turn the CourtListener lookups into passages any model or MCP can answer.
# usage: python3 build_tasks.py
import json
import os
import re
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
ITEMS = os.path.join(HERE, "items")
RESULTS = os.path.join(HERE, "results")
OUT = os.path.join(ITEMS, "tasks.jsonl")
META = "/home/graham/projects/courtlistener/pkg/caselaw_meta.db"

# Rows whose gold is wrong, duplicated, or not a legal answer,
# plus passages the CourtListener arm already passes. Those passes are
# replaced in build_harder.py. The gold was not retuned to flip them.
DROP = {
    "p07-coverage",  # reporter number is a candidate, not gold
    "dca-6-1", "dca-6-2",  # 1993 and 1994, before the Sixth DCA existed
    "dca-6-4",  # cluster caption and docket caption disagree
    "vend-04", "vend-05", "vend-06", "vend-07", "vend-08",  # one page, six orders
    "c8-02",  # overlay page does not match the reporter page on the case
    "ct-vt",  # trailing space is not a Bluebook answer a string match can see
    "ct-flacir2", "ct-flacir3",  # the stored cite is only "2nd" / "3rd"
    # CourtListener already returns a passing answer.
    "c9-01", "c9-02", "c9-03", "c9-04", "c9-05", "c9-06", "c9-07", "c9-08",
    "p06-fabrication",
    "c5-01", "c5-02", "c5-03", "c5-04", "c5-05", "c5-07", "c5-08",  # c5-06 stays
    "c3-01", "c3-02", "c3-03", "c3-04", "c3-05", "c3-06", "c3-07", "c3-08",
    "c2-01", "c2-02", "c2-03", "c2-04", "c2-05", "c2-06", "c2-07", "c2-08",
    # No saved reply, and a CourtListener answer would pass.
    "p01-control", "p02-name-alone", "p08-twin", "p09-statute",
}

# The question names the department, so the gold is one form and not a guess.
COURT_QUESTION = {
    "ct-nyappdiv": "Give the Bluebook court abbreviation for the New York Appellate Division, Second Department.",
    "ct-illappct": "Give the Bluebook court abbreviation for the Illinois Appellate Court, First District.",
    "ct-ohioctapp": "Give the Bluebook court abbreviation for the Ohio Court of Appeals, Tenth District.",
    "ct-texapp": "Give the Bluebook court abbreviation for the Texas Court of Appeals for the Fourteenth District, sitting in Houston.",
    "ct-cal1": "Give the Bluebook court abbreviation for the California Court of Appeal. The reporter series does not go in the court name.",
    "ct-cal2": "Give the Bluebook court abbreviation for the California Court of Appeal. The reporter series does not go in the court name.",
    "ct-cal3": "Give the Bluebook court abbreviation for the California Court of Appeal. The reporter series does not go in the court name.",
    "ct-cal4": "Give the Bluebook court abbreviation for the California Court of Appeal. The reporter series does not go in the court name.",
    "ct-cal5": "Give the Bluebook court abbreviation for the California Court of Appeal. Cal. App. 5th is the reporter, not the court.",
    "ct-cal6": "Give the Bluebook court abbreviation for the California Court of Appeal. The reporter series does not go in the court name.",
}

REJECTION = [
    "not found",
    "does not exist",
    "may be incorrect",
    "no such case",
    "cannot find",
]

TREATMENT = ["overruled", "receded", "abrogated", "no longer good law"]
UNPUBLISHED = ["unpublished", "not precedential", "nonprecedential", "not binding", "not citable"]
QUOTE_FLAG = ["garbled", "ocr", "corrupt", "not reliable", "unreliable", "not safe to quote", "do not quote"]


def load(name):
    path = os.path.join(ITEMS, name)
    return [json.loads(line) for line in open(path) if line.strip()]


def find_result(iid):
    for dirpath, _, files in os.walk(RESULTS):
        if iid + ".txt" in files:
            return os.path.join(dirpath, iid + ".txt")
    return None


def court_record(iid):
    path = os.path.join(RESULTS, "20261021-courts", iid + ".txt")
    if not os.path.exists(path):
        return {}
    return json.loads(open(path).read())


def reporter_cites(con, cluster_id):
    rows = con.execute(
        "select volume, reporter, page from citations where cluster_id=?",
        (cluster_id,),
    ).fetchall()
    out = []
    for volume, reporter, page in rows:
        rep = reporter or ""
        up = rep.upper()
        if up == "WL" or "LEXIS" in up or up == "WESTLAW":
            continue
        if volume and page:
            out.append(f"{volume} {rep} {page}".strip())
    # unique, stable
    seen = []
    for cite in out:
        if cite not in seen:
            seen.append(cite)
    return seen


def twin_names(iid, fallback):
    path = find_result(iid)
    names = []
    if path:
        for line in open(path):
            line = line.strip()
            if line.startswith("- ") and "(cluster_id=" in line:
                names.append(line[2:].split(" (cluster_id=")[0].strip())
    if len(names) >= 2:
        return names[:2]
    return [fallback] if fallback else []


def ocr_snippet(iid):
    path = find_result(iid)
    if not path:
        return ""
    raw = open(path).read()
    key = '"plain_text": "'
    i = raw.find(key)
    if i < 0:
        return ""
    frag = raw[i + len(key):]
    # The saved body is cut off mid-string. Drop a trailing broken escape.
    frag = re.sub(r"\\u[0-9a-fA-F]{0,3}$", "", frag)
    frag = re.sub(r"\\$", "", frag)
    frag = "".join(ch for ch in frag if ch >= " " or ch == "\t")
    try:
        text = json.loads('"' + frag + '"')
    except json.JSONDecodeError:
        text = frag.replace("\\n", " ")
    text = " ".join(text.split())
    return text[:240]


def task(iid, klass, text, gold):
    gold = dict(gold)
    gold.setdefault("note", "")
    return {"id": iid, "class": klass, "text": text.strip(), "gold": gold}


def from_courts():
    rows = []
    for raw in load("courts.jsonl"):
        if raw["id"] in DROP:
            continue
        g = raw["gold"]
        wrong = g.get("wrong") or ""
        right = g.get("right") or ""
        if raw["id"] in COURT_QUESTION:
            text = COURT_QUESTION[raw["id"]]
        elif wrong.strip():
            text = "Correct this court abbreviation to Bluebook form: " + wrong.strip() + "."
        else:
            rec = court_record(raw["id"])
            name = rec.get("full_name") or rec.get("short_name") or raw["court_id"]
            text = "Give the Bluebook abbreviation for this court: " + name + "."
        rows.append(task(raw["id"], "bluebook", text, {
            "right": [right] if right else [],
            "wrong": [wrong] if wrong.strip() else [],
            "note": g.get("why") or "",
        }))
    return rows


def from_bluebook():
    rows = []
    for raw in load("bluebook.jsonl"):
        if raw["id"] in DROP:
            continue
        g = raw["gold"]
        if raw["class"] == "bluebook_court":
            cite = g["cite"]
            name = g.get("case_name") or ""
            # The passage does not hand the system the corrected parenthetical.
            text = f"Give the Bluebook citation for {name}, {cite}, including the court."
            rows.append(task(raw["id"], "bluebook", text, {
                "right": [g["parenthetical"]],
                "wrong": ["Fla. Dist. Ct. App."],
                "note": "numbered Florida DCA form",
            }))
        elif raw["class"] == "opinion_cite":
            rows.append(task(raw["id"], "coverage", raw["text"], {
                "right": [g["cite"]],
                "absent": REJECTION,
                "note": "reporter cite taken from a citing opinion",
            }))
        elif raw["class"] == "vendor_when_official":
            rows.append(task(raw["id"], "vendor", raw["text"], {
                "right": [g["official"]],
                "forbid_vendor": True,
                "note": "reporter cite exists; a WL or LEXIS cite is a miss",
            }))
    return rows


def from_fixes(con):
    rows = []
    for raw in load("from_fixes.jsonl"):
        if raw["id"] in DROP or raw["id"].endswith("-status"):
            continue
        g = raw["gold"]
        klass = raw["class"]
        text = (raw.get("text") or "").strip()
        if klass == "coverage":
            text = text.replace("Hawai\u00e2\u20ac\u02dci", "Hawai'i")
            rows.append(task(raw["id"], "coverage", text, {
                "right": [g["cite"]],
                "absent": REJECTION,
                "note": "reporter cite is real and was missing from the index",
            }))
        elif klass == "wrong_index":
            rows.append(task(raw["id"], "wrong_cite", text, {
                "reject": True,
                "note": "this name was removed from this reporter cite",
            }))
        elif klass == "twin":
            names = twin_names(raw["id"], g.get("case_name"))
            rows.append(task(raw["id"], "twin", text, {
                "right": names,
                "note": "two cases share the cite",
            }))
        elif klass == "treatment":
            if g.get("signal"):
                words = TREATMENT
                note = g.get("signal")
            else:
                words = UNPUBLISHED
                note = "unpublished, stored as published"
            rows.append(task(raw["id"], "treatment", text, {
                "any_of": words,
                "note": note,
            }))
        elif klass == "pagination":
            rows.append(task(raw["id"], "pagination", text, {
                "right": [g["real_cite"]],
                "note": "printed page " + g.get("printed", "") + " is not the first page",
            }))
        elif klass == "misprint":
            rows.append(task(raw["id"], "misprint", text, {
                "right": [g["real_cite"]],
                "note": "one-digit miss; name the real cite",
            }))
        elif klass == "vendor":
            cites = reporter_cites(con, g.get("cluster_id"))
            if cites:
                rows.append(task(raw["id"], "vendor", text, {
                    "any_right": cites,
                    "forbid_vendor": True,
                    "note": "a reporter cite exists for this Westlaw or LEXIS number",
                }))
            else:
                rows.append(task(raw["id"], "vendor", text, {
                    "right": [g["case_name"]],
                    "absent": REJECTION,
                    "note": "no reporter cite; the case still has to be found",
                }))
        elif klass == "caption":
            rows.append(task(raw["id"], "caption", text, {
                "right": [g["canonical_name"]],
                "note": "caption form",
            }))
        elif klass == "ocr":
            snippet = ocr_snippet(raw["id"])
            if not snippet:
                continue
            q = "Is this a reliable quotation? If it is garbled, say so.\n\n" + snippet
            rows.append(task(raw["id"], "quotation", q, {
                "any_of": QUOTE_FLAG,
                "note": "opinion text still contains the garble",
            }))
    return rows


def from_harder():
    path = os.path.join(ITEMS, "harder.jsonl")
    if not os.path.exists(path):
        return []
    rows = []
    for raw in load("harder.jsonl"):
        rows.append(task(raw["id"], raw["class"], raw["text"], raw["gold"]))
    return rows


def from_pilot():
    rows = []
    spec = {
        "p01-control": ("control", {"right": ["Brown", "347 U.S. 483"], "absent": REJECTION, "note": "real cite"}),
        "p02-name-alone": ("caption", {"right": ["Brown"], "note": "the cite is Brown, not Smith v. Jones"}),
        "p03-name-collapse": ("caption", {
            "right": ["Brown"],
            "any_of": ["does not match", "wrong name", "not the name", "not this case", "different case"],
            "note": "the second name on the same cite is dropped, with no warning",
        }),
        "p04-interior": ("pagination", {"right": ["347 U.S. 483"], "note": "347 U.S. 484 is an interior page of Brown"}),
        "p05-treatment": ("treatment", {"any_of": TREATMENT, "note": "overruled"}),
        "p06-fabrication": ("control", {"reject": True, "note": "not a case"}),
        "p08-twin": ("twin", {"right": ["Google LLC v. Oracle America, Inc."], "any_of": ["4871034", "4870762", "two cases", "ambiguous", "another cluster"], "note": "two clusters share 593 U.S. 1"}),
        "p09-statute": ("statute", {"right": ["1983"], "absent": REJECTION + ["no citations found"], "note": "the statute has to be recognized"}),
        "p10-rule": ("statute", {"right": ["1.140"], "absent": REJECTION + ["no citations found"], "note": "the rule has to be recognized"}),
    }
    by_id = {r["id"]: r for r in load("pilot.jsonl")}
    for iid, (klass, gold) in spec.items():
        if iid in DROP:
            continue
        raw = by_id[iid]
        rows.append(task(iid, klass, raw["text"], gold))
    return rows


def main():
    con = sqlite3.connect("file:" + META + "?mode=ro", uri=True)
    rows = from_courts() + from_bluebook() + from_fixes(con) + from_harder() + from_pilot()
    # Stable order: class, then id.
    rows.sort(key=lambda r: (r["class"], r["id"]))
    with open(OUT, "w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} {OUT}")


if __name__ == "__main__":
    main()
