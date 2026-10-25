# Clean control items (v1.1): ordinary, correct citations where the right answer
# is "this citation is correct as written". They measure an arm's false-positive
# rate: a checker that calls every cite a misprint or a fabrication fails them.
# Does not call the network. Writes items/controls.jsonl.
#
# Every row was verified on 2026-10-25 against the live Syfert MCP (check_brief
# resolved each cite to one cluster with a matching party name); the cluster id
# is the evidence. Half are casebook cases a bare model knows
# (bare_model_answerable); half are ordinary reported cases nobody memorises,
# so an arm cannot tell a control from a trap by how famous the case is.
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "items", "controls.jsonl")
CHECKED = "2026-10-25"

REJECTION = [
    "not found",
    "does not exist",
    "may be incorrect",
    "no such case",
    "cannot find",
    "could not find",
    "fabricated",
]
# Phrases that would mean the arm "corrected" a correct cite. Read on the ANSWER line only.
FALSE_CORRECTION = [
    "misprint",
    "typo",
    "interior page",
    "not the first page",
    "wrong series",
    "wrong reporter",
    "wrong page",
    "wrong volume",
    "should be",
    "does not match",
    "name mismatch",
    "overruled",
    "abrogated",
    "receded",
    "no longer good law",
    "unpublished",
]

# (id, passage name, cite, cluster_id, court and year, bare_model_answerable)
CONTROLS = [
    ("co-01", "Erie Railroad Co. v. Tompkins", "304 U.S. 64", 103012, "U.S. 1938", True),
    ("co-02", "Celotex Corp. v. Catrett", "477 U.S. 317", 111722, "U.S. 1986", True),
    ("co-03", "Daubert v. Merrell Dow Pharmaceuticals, Inc.", "509 U.S. 579", 112903, "U.S. 1993", True),
    ("co-04", "International Shoe Co. v. Washington", "326 U.S. 310", 104200, "U.S. 1945", True),
    ("co-05", "Palsgraf v. Long Island Railroad Co.", "248 N.Y. 339", 3602780, "N.Y. 1928", True),
    ("co-06", "Lucy v. Zehmer", "196 Va. 493", 1305339, "Va. 1954", True),
    ("co-07", "Garratt v. Dailey", "46 Wash. 2d 197", 1169600, "Wash. 1955", True),
    ("co-08", "Katko v. Briney", "183 N.W.2d 657", 2151117, "Iowa 1971", True),
    ("co-09", "Hoffman v. Jones", "280 So. 2d 431", 1704250, "Fla. 1973", True),
    ("co-10", "Vokes v. Arthur Murray, Inc.", "212 So. 2d 906", 1101421, "Fla. 2d DCA 1968", True),
    ("co-11", "United States v. Carroll Towing Co.", "159 F.2d 169", 1565896, "2d Cir. 1947", True),
    ("co-12", "Mata v. Avianca, Inc.", "678 F. Supp. 3d 443", 9885417, "S.D.N.Y. 2023", True),
    ("co-13", "In re Norris", "192 B.R. 863", 1811601, "Bankr. W.D. La. 1995", False),
    ("co-14", "In re Reinstatement of Holleman", "826 So. 2d 1243", 1630824, "Miss. 2002", False),
    ("co-15", "In re Christopher J.", "505 A.2d 795", 2323178, "Me. 1986", False),
    ("co-16", "In re Marriage of Pennington", "14 P.3d 764", 2516443, "Wash. 2000", False),
    ("co-17", "In re Pena", "155 F.3d 1108", 757846, "9th Cir. 1998", False),
    ("co-18", "Restucci v. Spencer", "249 F. Supp. 2d 33", 2460880, "D. Mass. 2003", False),
    ("co-19", "Crosby v. Clark", "132 Cal. 1", 3302278, "Cal. 1901", False),
    ("co-20", "Benavides v. Hunt", "79 Tex. 383", 5081313, "Tex. 1891", False),
    ("co-21", "Capital City Brick Co. v. Atlanta Ice & Coal Co.", "5 Ga. App. 436", 5751169, "Ga. Ct. App. 1909", False),
    ("co-22", "United States v. Denton", "611 F.3d 646", 150347, "9th Cir. 2010", False),
    ("co-23", "Securities & Exchange Commission v. Vescor Capital Corp.", "599 F.3d 1189", 8440583, "10th Cir. 2010", False),
    ("co-24", "Meijer, Inc. v. Ferring B.V.", "585 F.3d 677", 8440519, "2d Cir. 2009", False),
]


def main():
    rows = []
    for iid, name, cite, cid, where, bare in CONTROLS:
        row = {
            "id": iid,
            "class": "control",
            "kind": "control",
            "tool": "analyze_citations",
            "text": f"{name}, {cite}.",
            "gold": {
                "right": [cite],
                "absent": REJECTION + FALSE_CORRECTION,
                "note": "correct as written; " + where,
            },
            "evidence": {
                "source": "syfert.com MCP check_brief, " + CHECKED,
                "cluster_id": cid,
                "court_year": where,
            },
        }
        if bare:
            row["bare_model_answerable"] = True
        rows.append(row)
    with open(OUT, "w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("wrote", len(rows), OUT)


if __name__ == "__main__":
    main()
