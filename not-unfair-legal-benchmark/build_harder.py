# Rows chosen 2026-10-22 from the CourtListener citation table on this machine.
# Does not call the network. Writes items/harder.jsonl.
#
# series: a Florida DCA opinion whose Southern Reporter cite is also stored as
#   "Fla. L. Weekly Fed. D". That series is the federal weekly. The state
#   weekly is not on the cluster. Districts are fl_dca_districts.db.
# history: an S. Ct., U.S., or L. Ed. page that is an orders page or a cert
#   denial, and that CourtListener also attaches to the lower-court opinion.
# bluebook: citation_string values the earlier court list did not rewrite
#   (SCOTUS, Tax Ct., Ct. Intl. Trade), plus one Court of Criminal Appeals
#   case filed under texapp (docket PD-1453-15, 479 S.W.3d 422).
# statute: rule forms and one cite that is not a section. Kept only if the
#   CourtListener reply misses them; score_saved is the check.
# zero: replacements for passages the CourtListener arm already passed.
#   Interior pages that come back NOT FOUND, captions that still carry a
#   looseleaf name or a list literal, two truncated captions, and orders
#   pages filed under the court below. Each was a miss on server 9386476.
# treatment (v1.1): four overruled cases spread across reporters and decades,
#   each verified on 2026-10-25 against the live treatment tool, with the
#   overruling case recorded in evidence.
#
# v1.1 (2026-10-25, see CHANGELOG.md): every row carries an evidence field.
# Caption gold is the surname (Bluebook 10.2.1(g)); history gold names the
# cases on the page (read from the saved CourtListener reply) instead of the
# words "Supreme Court" / "certiorari"; h-421 takes any one of the five names.
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "items", "harder.jsonl")
RESULTS = os.path.join(HERE, "results")
CHECKED = "2026-10-25"

HISTORY = [
    "cert. denied",
    "cert denied",
    "certiorari denied",
    "denial of certiorari",
    "denied certiorari",
    "denying certiorari",
    "petition for certiorari",
    "petition for a writ of certiorari",
    "writ of certiorari",
    "orders page",
    "order list",
    "memorandum decision",
    "summary disposition",
    "substantial federal question",
    "dismissed for want",
]
REJECTION = [
    "not found",
    "does not exist",
    "may be incorrect",
    "no such case",
    "cannot find",
    "no citations found",
]
TREATMENT = ["overruled", "receded", "abrogated", "no longer good law", "superseded", "not good law", "disapproved"]

# (id, name, bad series cite, real cite, court, cluster_id)
SERIES = [
    ("flw-01", "Hall v. State", "15 Fla. L. Weekly Fed. D 1032", "562 So. 2d 714", "Fla. 1st DCA", 7649951),
    ("flw-02", "Williams v. State", "15 Fla. L. Weekly Fed. D 1620", "562 So. 2d 844", "Fla. 1st DCA", 7649984),
    ("flw-03", "Pease v. State", "15 Fla. L. Weekly Fed. D 2949", "570 So. 2d 1116", "Fla. 2d DCA", 7653742),
    ("flw-04", "Hapney v. Central Garage, Inc.", "16 Fla. L. Weekly Fed. D 1344", "579 So. 2d 127", "Fla. 2d DCA", 1831917),
    ("flw-05", "Bodek v. Gulliver Academy, Inc.", "20 Fla. L. Weekly Fed. D 1399", "659 So. 2d 354", "Fla. 3d DCA", 7753068),
    ("flw-06", "Acevedo v. Caribbean Transp., Inc.", "21 Fla. L. Weekly Fed. D 1147", "673 So. 2d 170", "Fla. 3d DCA", 1657255),
    ("flw-07", "Regueiro v. State", "17 Fla. L. Weekly Fed. D 987", "596 So. 2d 175", "Fla. 4th DCA", 7665193),
    ("flw-08", "Johnson v. State", "17 Fla. L. Weekly Fed. D 2537", "608 So. 2d 138", "Fla. 4th DCA", 7689256),
    ("flw-09", "Beebe v. American Ambassador Cas. Co.", "20 Fla. L. Weekly Fed. D 1877", "659 So. 2d 701", "Fla. 5th DCA", 1893469),
    ("flw-10", "M.J.C. v. State", "21 Fla. L. Weekly Fed. D 2301", "681 So. 2d 1203", "Fla. 5th DCA", 7763291),
]


def mcp_evidence(cluster_id, note="", **extra):
    ev = {"source": "syfert.com MCP (find_case / check_citation), " + CHECKED, "cluster_id": cluster_id}
    if note:
        ev["note"] = note
    ev.update(extra)
    return ev


rows = []
for iid, name, bad, good, court, cid in SERIES:
    rows.append({
        "id": iid,
        "class": "series",
        "tool": "analyze_citations",
        "text": (
            f"Give the citation for {name}, {bad}, including the court. "
            "Use the Florida form for a district court of appeal (Fla. R. App. P. 9.800)."
        ),
        "gold": {
            "right": [good, court],
            "wrong": ["Fla. L. Weekly Fed. D"],
            "note": "state DCA opinion stored under the federal weekly series",
        },
        "evidence": mcp_evidence(cid, "Southern Reporter cite and numbered district confirmed; the weekly cite is the federal series"),
    })


def find_result(iid):
    for dirpath, _, files in os.walk(RESULTS):
        if iid + ".txt" in files:
            return os.path.join(dirpath, iid + ".txt")
    return None


_LISTED = re.compile(r"^- (.+?) \(cluster_id=(\d+); (\d{4}-\d{2}-\d{2}); cited by (\d+)\)")


def listed_cases(iid):
    """(name, cluster_id, date) for every case the saved CourtListener reply attaches to the page."""
    path = find_result(iid)
    out = []
    if not path:
        return out
    for line in open(path):
        m = _LISTED.match(line.strip())
        if m:
            out.append((m.group(1).strip(), int(m.group(2)), m.group(3)))
    return out


def history(iid, text, note, right=None, any_right=None, extra_right=None):
    """An orders page. Gold: a cert./orders word plus one of the cases on the page.

    right stays for the three items where one lower-court cite is the answer.
    Otherwise any_right is every case the saved reply lists on the page, plus
    extra_right (the lower-court reporter cite the page is wrongly attached to).
    """
    listed = listed_cases(iid)
    names = []
    for name, _, _ in listed:
        if name not in names:
            names.append(name)
    gold = {"any_of": HISTORY, "note": note}
    if right:
        gold["right"] = right
    else:
        alts = list(any_right or [])
        for n in names:
            if n not in alts:
                alts.append(n)
        for x in (extra_right or []):
            if x not in alts:
                alts.append(x)
        gold["any_right"] = alts
    rows.append({
        "id": iid,
        "class": "history",
        "tool": "analyze_citations",
        "text": text,
        "gold": gold,
        "evidence": {
            "source": "CourtListener analyze_citations reply saved 2026-10-22 (results/), server 9386476",
            "clusters": [{"name": n, "cluster_id": c, "date_filed": d} for n, c, d in listed],
        },
    })


history(
    "h-67",
    "67 S. Ct. 358.",
    "orders page also attached to Broyles v. State, 173 P.2d 235",
    extra_right=["173 P.2d 235"],
)
history(
    "h-68a",
    "68 S. Ct. 1333.",
    "orders page also attached to Ex parte Allen, 192 P.2d 289",
    extra_right=["192 P.2d 289"],
)
history(
    "h-68b",
    "68 S. Ct. 351.",
    "orders page also attached to SEC v. Transamerica, 67 F. Supp. 326",
    extra_right=["67 F. Supp. 326"],
)
history(
    "h-110",
    "110 S. Ct. 1128.",
    "orders page also attached to Oxley, 794 P.2d 742",
    extra_right=["794 P.2d 742"],
)
history(
    "h-113",
    "113 S. Ct. 2049.",
    "cert. denied cite stored as the cite of the Eleventh Circuit opinion",
    right=["991 F.2d 663"],
)
history(
    "h-85",
    "85 L. Ed. 458.",
    "L. Ed. cert. denial stored as the cite of Murphy v. Cady, 30 F. Supp. 466",
    right=["30 F. Supp. 466"],
)
history(
    "h-102",
    "102 S. Ct. 671.",
    "1981 orders page also attached to a 1996 case, 102 F.3d 671",
    any_right=["Banerjee", "United Steelworkers", "McCausland", "Vetco", "Vichos"],
    extra_right=["102 F.3d 671"],
)
history(
    "h-114",
    "114 S. Ct. 237.",
    "orders page; one cluster is filed in the Veterans Court",
)
history(
    "h-421",
    "421 U.S. 901.",
    "five Supreme Court dismissals filed in W.D. Pa.; any one of the five names is enough (v1.1)",
    any_right=["Wicks", "Harris", "Roemer", "Rivers", "Dickinson"],
)

BLUEBOOK_RULE = "The Bluebook (21st ed.) T1 (courts) and T7 (court names); B10.1.3"

rows.append({
    "id": "ct-txcca",
    "class": "bluebook",
    "tool": "analyze_citations",
    "text": "Give the Bluebook citation for 479 S.W.3d 422, docket PD-1453-15, including the court.",
    "gold": {
        "right": ["Tex. Crim. App.", "479 S.W.3d 422"],
        "wrong": ["Tex. App."],
        "note": "PD docket is the Court of Criminal Appeals; the cluster is filed under texapp",
    },
    "evidence": mcp_evidence(4294338, "Bullock v. State, Tex. Crim. App., 2015-10-20, docket PD-1453-15"),
})
rows.append({
    "id": "ct-scotus",
    "class": "bluebook",
    "tool": "court",
    "court_id": "scotus",
    "text": "Correct this court abbreviation to Bluebook form: SCOTUS.",
    "gold": {
        "right": ["U.S."],
        "wrong": ["SCOTUS"],
        "note": "citation_string on the Supreme Court is SCOTUS",
    },
    "evidence": {"source": BLUEBOOK_RULE},
})
rows.append({
    "id": "ct-tax",
    "class": "bluebook",
    "tool": "court",
    "court_id": "tax",
    "text": "Correct this court abbreviation to Bluebook form: Tax Ct.",
    "gold": {
        "right": ["T.C."],
        "wrong": ["Tax Ct."],
        "note": "Tax Court abbreviation is T.C.",
    },
    "evidence": {"source": BLUEBOOK_RULE},
})
rows.append({
    "id": "ct-cit",
    "class": "bluebook",
    "tool": "court",
    "court_id": "cit",
    "text": "Correct this court abbreviation to Bluebook form: Ct. Intl. Trade.",
    "gold": {
        "right": ["Ct. Int'l Trade"],
        "wrong": ["Ct. Intl. Trade"],
        "note": "Bluebook spells Int'l",
    },
    "evidence": {"source": BLUEBOOK_RULE},
})

for iid, text, right, url in (
    ("st-frcp", "Fed. R. Civ. P. 56.", ["56"], "https://syfert.com/federal-rules/civil/rule-56.html"),
    ("st-frcrim", "Fla. R. Crim. P. 3.850.", ["3.850"], "https://syfert.com/florida/rules-criminal-procedure/rule-3.850/"),
    ("st-fre", "Fed. R. Evid. 702.", ["702"], "https://syfert.com/federal-rules/evidence/rule-702.html"),
):
    rows.append({
        "id": iid,
        "class": "statute",
        "tool": "analyze_citations",
        "text": text,
        "gold": {
            "right": right,
            "absent": REJECTION,
            "note": "the rule has to be recognized",
        },
        "evidence": {"source": "syfert.com MCP check_citation, " + CHECKED, "verified": True, "url": url},
    })
rows.append({
    "id": "st-fake",
    "class": "statute",
    "tool": "analyze_citations",
    "text": "99 U.S.C. § 99999.",
    "gold": {"reject": True, "note": "not a section"},
    "evidence": {"source": "the United States Code has 54 titles; there is no title 99"},
})

# Famous interior pages the lookup does not fold back to the first page.
# Pages it does fold (Mapp, Terry, Katz, Sullivan, Brandenburg, Casey) are
# not here. 347 U.S. 484 is already p04-interior.
# 559 U.S. 460 and 559 U.S. 573 already return the corrected case names
# on server 9386476, so those captions are not planted.
for iid, text, first, note, cid in (
    ("pin-02", "467 U.S. 838.", "467 U.S. 837", "interior page of Chevron", 111221),
    ("pin-03", "384 U.S. 437.", "384 U.S. 436", "interior page of Miranda", 107252),
    ("pin-04", "410 U.S. 114.", "410 U.S. 113", "interior page of Roe", 108713),
    ("pin-10", "514 U.S. 550.", "514 U.S. 549", "interior page of Lopez", 117927),
    ("pin-11", "428 U.S. 154.", "428 U.S. 153", "interior page of Gregg", 109532),
    ("pin-12", "554 U.S. 571.", "554 U.S. 570", "interior page of Heller", 145777),
    ("pin-14", "597 U.S. 216.", "597 U.S. 215", "interior page of Dobbs", 6481357),
):
    rows.append({
        "id": iid,
        "class": "pagination",
        "tool": "analyze_citations",
        "text": text,
        "gold": {"right": [first], "note": note},
        "evidence": mcp_evidence(cid, "first page of the reported case"),
        "bare_model_answerable": True,
    })

# Captions stored with a looseleaf service name in front. Gold is the surname
# (Bluebook 10.2.1(g) omits given names and initials), so "Doe v. Blum" passes.
for iid, cite, parties, stored, cid in (
    ("cap-svc-01", "729 F.2d 186", ["Doe", "Blum"], "Medicare&medicaid Gu 33,639 Jane Doe v. Barbara Blum", 432014),
    ("cap-svc-02", "740 F.2d 100", ["Mayburg"], "6 soc.sec.rep.ser. 142, Medicare&medicaid Gu 34,082 Rose Mayburg v. Secretary of Health and Human Services", 439212),
    ("cap-svc-03", "740 F.2d 1491", ["Diaz"], "Medicare&medicaid Gu 34,122 United States of America v. Mario Diaz, M.D.", 439972),
    ("cap-svc-04", "740 F.2d 1493", ["Kass"], "Medicare&medicaid Gu 34,121 United States of America v. Donald M. Kass, M.D.", 439973),
    ("cap-svc-05", "752 F.2d 578", ["Hilliard"], "Medicare&medicaid Gu 34,521 United States of America v. Anneliese E. Hilliard", 446651),
    ("cap-svc-06", "755 F.2d 653", ["Bushman"], "Medicare&medicaid Gu 34,507 Richard D. Bushman v. Joseph E. Seiler", 448213),
    ("cap-svc-07", "755 F.2d 870", ["Caldwell"], "8 soc.sec.rep.ser. 369, Medicare&medicaid Gu 34,552 Mollie T. Caldwell v. George T. Wallace, Governor of the State of Alabama", 448253),
    ("cap-svc-08", "757 F.2d 87", ["Bedford"], "9 soc.sec.rep.ser. 114, Medicare&medicaid Gu 34,538 Bedford County General Hospital v. Margaret Heckler, Secretary of Health and Human Services", 449318),
):
    rows.append({
        "id": iid,
        "class": "caption",
        "tool": "analyze_citations",
        "text": f"Give the Bluebook case name for {cite}.",
        "gold": {
            "right": parties,
            "wrong": ["Medicare&medicaid", "soc.sec.rep.ser."],
            "note": "looseleaf service cite stored in the caption; surname is enough (10.2.1(g))",
        },
        "evidence": mcp_evidence(cid, "stored caption: " + stored),
    })

# Captions stored as a Python list literal. Gold accepts the full name and the
# T6 abbreviation where one applies.
for iid, cite, right, any_right, stored, cid in (
    ("cap-list-01", "4 F. Supp. 3d 222", ["Flythe"], None, "['Flythe v. District of Columbia']", 2658346),
    ("cap-list-02", "31 F. Supp. 3d 124", None, ["Corporate Systems Resources", "Corp. Sys. Res", "Corporate Sys. Res"], "['Corporate Systems Resources v. Washington Metropolitan Area Transit Authority']", 2658347),
    ("cap-list-03", "31 F. Supp. 3d 101", ["Alkasabi"], None, "['Alkasabi v. Washington Mutual Bank, F.a.']", 2658349),
    ("cap-list-04", "28 F. Supp. 3d 47", ["Hill v. Gray"], None, "['Hill v. Gray']", 2658352),
    ("cap-list-05", "30 F. Supp. 3d 25", ["Associated Builders"], None, "['Associated Builders and Contractors, Inc. v. Shiu']", 2658353),
    ("cap-list-06", "30 F. Supp. 3d 67", None, ["American Immigration Council", "Am. Immigration Council", "Am. Immigr. Council"], "['American Immigration Council v. United States Department of Homeland Security']", 2658354),
):
    gold = {"wrong": ["['"], "note": "caption stored as a list literal"}
    if right:
        gold["right"] = right
    if any_right:
        gold["any_right"] = any_right
    rows.append({
        "id": iid,
        "class": "caption",
        "tool": "analyze_citations",
        "text": f"Give the Bluebook case name for {cite}.",
        "gold": gold,
        "evidence": mcp_evidence(cid, "stored caption: " + stored),
    })

rows.append({
    "id": "cap-front-01",
    "class": "caption",
    "tool": "analyze_citations",
    "text": "Give the Bluebook case name for 442 S.W.3d 805.",
    "gold": {"right": ["Ex parte", "Hartfield"], "note": "habeas caption stored as In re"},
    "evidence": mcp_evidence(3082117, "opinion caption: Ex parte Jerry Hartfield; CourtListener stores 'In re Jerry Hartfield'"),
})
rows.append({
    "id": "cap-front-02",
    "class": "caption",
    "tool": "analyze_citations",
    "text": "Give the Bluebook case name for 183 F. Supp. 601.",
    "gold": {
        "any_right": ["Arpon", "Vda de Samala", "Vda. de Samala", "Viuda de Samala"],
        "note": "caption front truncated: the plaintiff is Eugenia Arpon Vda. de Samala; CourtListener stores 'de Samala v. United States'",
    },
    "evidence": mcp_evidence(8747572, "opinion caption: Eugenia Arpon Vda de Samala v. United States (D.D.C. 1960)"),
})

for iid, text in (
    ("h-ord-01", "114 S. Ct. 269."),
    ("h-ord-02", "510 U.S. 1195."),
    ("h-ord-03", "511 U.S. 1108."),
    ("h-ord-04", "512 U.S. 1206."),
    ("h-ord-05", "519 U.S. 1098."),
    ("h-ord-06", "520 U.S. 1245."),
    ("h-ord-07", "521 U.S. 1103."),
    ("h-ord-08", "522 U.S. 860."),
    ("h-ord-09", "114 S. Ct. 407."),
):
    history(iid, text, "Supreme Court order filed under the court below")

# v1.1 treatment rows: overruled cases across reporters and decades. Each was
# red on the live treatment tool on 2026-10-25 with the overruling case named.
for iid, text, by, by_cid, cid, bare in (
    ("t-bowers", "Bowers v. Hardwick, 478 U.S. 186.", "Lawrence v. Texas, 539 U.S. 558 (2003)", 130160, 111738, True),
    ("t-quill", "Quill Corp. v. North Dakota, 504 U.S. 298.", "South Dakota v. Wayfair, Inc., 585 U.S. 162 (2018)", 4509418, 112739, True),
    ("t-abood", "Abood v. Detroit Board of Education, 431 U.S. 209.", "Janus v. AFSCME, Council 31, 585 U.S. 878 (2018)", 4511640, 109661, True),
    ("t-azzarello", "Azzarello v. Black Bros. Co., 391 A.2d 1020.", "Tincher v. Omega Flex, Inc., 104 A.3d 328 (Pa. 2014)", 2753363, 1957128, False),
):
    row = {
        "id": iid,
        "class": "treatment",
        "tool": "analyze_citations",
        "text": text,
        "gold": {"any_of": TREATMENT, "verdict_line": True, "note": "overruled by " + by},
        "evidence": {
            "source": "syfert.com MCP get_treatment, " + CHECKED,
            "cluster_id": cid,
            "flag": "red",
            "overruled_by": by,
            "overruled_by_cluster_id": by_cid,
        },
    }
    if bare:
        row["bare_model_answerable"] = True
    rows.append(row)

with open(OUT, "w") as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
print("wrote", len(rows), OUT)
