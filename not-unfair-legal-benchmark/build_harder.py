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
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "items", "harder.jsonl")

HISTORY = [
    "cert. denied",
    "certiorari denied",
    "denial of certiorari",
    "certiorari",
    "orders page",
    "Supreme Court",
    "substantial federal question",
]
REJECTION = [
    "not found",
    "does not exist",
    "may be incorrect",
    "no such case",
    "cannot find",
    "no citations found",
]

SERIES = [
    ("flw-01", "Hall v. State", "15 Fla. L. Weekly Fed. D 1032", "562 So. 2d 714", "Fla. 1st DCA"),
    ("flw-02", "Williams v. State", "15 Fla. L. Weekly Fed. D 1620", "562 So. 2d 844", "Fla. 1st DCA"),
    ("flw-03", "Pease v. State", "15 Fla. L. Weekly Fed. D 2949", "570 So. 2d 1116", "Fla. 2d DCA"),
    ("flw-04", "Hapney v. Central Garage, Inc.", "16 Fla. L. Weekly Fed. D 1344", "579 So. 2d 127", "Fla. 2d DCA"),
    ("flw-05", "Bodek v. Gulliver Academy, Inc.", "20 Fla. L. Weekly Fed. D 1399", "659 So. 2d 354", "Fla. 3d DCA"),
    ("flw-06", "Acevedo v. Caribbean Transp., Inc.", "21 Fla. L. Weekly Fed. D 1147", "673 So. 2d 170", "Fla. 3d DCA"),
    ("flw-07", "Regueiro v. State", "17 Fla. L. Weekly Fed. D 987", "596 So. 2d 175", "Fla. 4th DCA"),
    ("flw-08", "Johnson v. State", "17 Fla. L. Weekly Fed. D 2537", "608 So. 2d 138", "Fla. 4th DCA"),
    ("flw-09", "Beebe v. American Ambassador Cas. Co.", "20 Fla. L. Weekly Fed. D 1877", "659 So. 2d 701", "Fla. 5th DCA"),
    ("flw-10", "M.J.C. v. State", "21 Fla. L. Weekly Fed. D 2301", "681 So. 2d 1203", "Fla. 5th DCA"),
]

rows = []
for iid, name, bad, good, court in SERIES:
    rows.append({
        "id": iid,
        "class": "series",
        "tool": "analyze_citations",
        "text": f"Give the Bluebook citation for {name}, {bad}, including the court.",
        "gold": {
            "right": [good, court],
            "wrong": ["Fla. L. Weekly Fed. D"],
            "note": "state DCA opinion stored under the federal weekly series",
        },
    })

def history(iid, text, note, right=None, any_right=None):
    gold = {"any_of": HISTORY, "note": note}
    if right:
        gold["right"] = right
    if any_right:
        gold["any_right"] = any_right
    rows.append({
        "id": iid,
        "class": "history",
        "tool": "analyze_citations",
        "text": text,
        "gold": gold,
    })

history(
    "h-67",
    "67 S. Ct. 358.",
    "orders page also attached to Broyles v. State, 173 P.2d 235",
)
history(
    "h-68a",
    "68 S. Ct. 1333.",
    "orders page also attached to Ex parte Allen, 192 P.2d 289",
)
history(
    "h-68b",
    "68 S. Ct. 351.",
    "orders page also attached to SEC v. Transamerica, 67 F. Supp. 326",
)
history(
    "h-110",
    "110 S. Ct. 1128.",
    "orders page also attached to Oxley, 794 P.2d 742",
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
)
history(
    "h-114",
    "114 S. Ct. 237.",
    "orders page; one cluster is filed in the Veterans Court",
)
history(
    "h-421",
    "421 U.S. 901.",
    "five Supreme Court dismissals filed in W.D. Pa.",
    right=["Wicks", "Harris", "Roemer", "Rivers", "Dickinson"],
)

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
})

for iid, text, right in (
    ("st-frcp", "Fed. R. Civ. P. 56.", ["56"]),
    ("st-frcrim", "Fla. R. Crim. P. 3.850.", ["3.850"]),
    ("st-fre", "Fed. R. Evid. 702.", ["702"]),
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
    })
rows.append({
    "id": "st-fake",
    "class": "statute",
    "tool": "analyze_citations",
    "text": "99 U.S.C. § 99999.",
    "gold": {"reject": True, "note": "not a section"},
})

# Famous interior pages the lookup does not fold back to the first page.
# Pages it does fold (Mapp, Terry, Katz, Sullivan, Brandenburg, Casey) are
# not here. 347 U.S. 484 is already p04-interior.
# 559 U.S. 460 and 559 U.S. 573 already return the corrected case names
# on server 9386476, so those captions are not planted.
for iid, text, first, note in (
    ("pin-02", "467 U.S. 838.", "467 U.S. 837", "interior page of Chevron"),
    ("pin-03", "384 U.S. 437.", "384 U.S. 436", "interior page of Miranda"),
    ("pin-04", "410 U.S. 114.", "410 U.S. 113", "interior page of Roe"),
    ("pin-10", "514 U.S. 550.", "514 U.S. 549", "interior page of Lopez"),
    ("pin-11", "428 U.S. 154.", "428 U.S. 153", "interior page of Gregg"),
    ("pin-12", "554 U.S. 571.", "554 U.S. 570", "interior page of Heller"),
    ("pin-14", "597 U.S. 216.", "597 U.S. 215", "interior page of Dobbs"),
):
    rows.append({
        "id": iid,
        "class": "pagination",
        "tool": "analyze_citations",
        "text": text,
        "gold": {"right": [first], "note": note},
    })

for iid, cite, party in (
    ("cap-svc-01", "729 F.2d 186", "Jane Doe v. Barbara Blum"),
    ("cap-svc-02", "740 F.2d 100", "Rose Mayburg"),
    ("cap-svc-03", "740 F.2d 1491", "Mario Diaz"),
    ("cap-svc-04", "740 F.2d 1493", "Donald M. Kass"),
    ("cap-svc-05", "752 F.2d 578", "Anneliese E. Hilliard"),
    ("cap-svc-06", "755 F.2d 653", "Richard D. Bushman"),
    ("cap-svc-07", "755 F.2d 870", "Mollie T. Caldwell"),
    ("cap-svc-08", "757 F.2d 87", "Bedford County General Hospital"),
):
    rows.append({
        "id": iid,
        "class": "caption",
        "tool": "analyze_citations",
        "text": f"Give the Bluebook case name for {cite}.",
        "gold": {
            "right": [party],
            "wrong": ["Medicare&medicaid"],
            "note": "looseleaf service cite stored in the caption",
        },
    })

for iid, cite, party in (
    ("cap-list-01", "4 F. Supp. 3d 222", "Flythe v. District of Columbia"),
    ("cap-list-02", "31 F. Supp. 3d 124", "Corporate Systems Resources"),
    ("cap-list-03", "31 F. Supp. 3d 101", "Alkasabi"),
    ("cap-list-04", "28 F. Supp. 3d 47", "Hill v. Gray"),
    ("cap-list-05", "30 F. Supp. 3d 25", "Associated Builders and Contractors"),
    ("cap-list-06", "30 F. Supp. 3d 67", "American Immigration Council"),
):
    rows.append({
        "id": iid,
        "class": "caption",
        "tool": "analyze_citations",
        "text": f"Give the Bluebook case name for {cite}.",
        "gold": {
            "right": [party],
            "wrong": ["['"],
            "note": "caption stored as a list literal",
        },
    })

for iid, cite, party, note in (
    ("cap-front-01", "442 S.W.3d 805", "Ex parte", "habeas caption stored as In re"),
    ("cap-front-02", "183 F. Supp. 601", "Eugenia Arpon", "caption front truncated"),
):
    rows.append({
        "id": iid,
        "class": "caption",
        "tool": "analyze_citations",
        "text": f"Give the Bluebook case name for {cite}.",
        "gold": {"right": [party], "note": note},
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

with open(OUT, "w") as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
print("wrote", len(rows), OUT)
