# Court-citation items planted from bluebookCourtCite() / bluebookCourtCiteForCase()
# in caselaw-tools/bbtrim_20261009/live_xeric_bluebook.php.
# Each row is one courts_lite id whose citation_string that code rewrites.
# usage: python3 build_courts.py
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "items", "courts.jsonl")

# (id, court_id, class, wrong, right, why)
# wrong is the string CourtListener stores. right is what the builder emits.
# v1.1: ALSO_RIGHT lists a second accepted form for the rows where the Bluebook
# itself allows or prefers a form other than the builder's (REVIEW_20261024 A3,
# A5; Bluebook rule 10.4(b) says not to add the department or district of an
# intermediate state court unless it matters). ct-hl is dropped in build_tasks.
ROWS = [
    # $courtFix: spelled-out states, missing periods, missing spaces, closed-up capitals.
    ("ct-ny", "ny", "court_string", "NY", "N.Y.", "New York Court of Appeals stored as NY"),
    ("ct-hl", "houseoflordsuk", "court_string", "HL", "H.L.", "House of Lords stored as HL"),
    ("ct-mdd", "mdd", "court_string", "D. Maryland", "D. Md.", "Maryland spelled out"),
    ("ct-mnd", "mnd", "court_string", "D. Minnesota", "D. Minn.", "Minnesota spelled out"),
    ("ct-pamd", "pamd", "court_string", "M.D. Penn.", "M.D. Pa.", "Pennsylvania abbreviated Penn."),
    ("ct-pamb", "pamb", "court_string", "Bankr. M.D. Penn.", "Bankr. M.D. Pa.", "bankruptcy court, Penn."),
    ("ct-nyed", "nyed", "court_string", "E.D.N.Y", "E.D.N.Y.", "missing period after Y"),
    ("ct-wvsd", "wvsd", "court_string", "S.D.W. Va", "S.D. W. Va.", "missing space and period"),
    ("ct-wvnd", "wvnd", "court_string", "N.D.W. Va.", "N.D. W. Va.", "missing space before Va."),
    ("ct-wvad", "wvad", "court_string", "D. W.Va.", "D. W. Va.", "Va. closed up"),
    ("ct-wvnb", "wvnb", "court_string", "Bankr. N.D.W. Va.", "Bankr. N.D. W. Va.", "missing space before Va."),
    ("ct-wvsb", "wvsb", "court_string", "Bankr. S.D.W. Va.", "Bankr. S.D. W. Va.", "missing space before Va."),
    ("ct-nyd", "nyd", "court_string", "D. N.Y.", "D.N.Y.", "space in D. N.Y."),
    ("ct-cob", "cob", "court_string", "Bankr.D. Colo.", "Bankr. D. Colo.", "missing space after Bankr."),
    ("ct-dcb", "dcb", "court_string", "Bankr. D.C.", "Bankr. D.D.C.", "D.C. bankruptcy is D.D.C."),
    ("ct-flsb", "flsb", "court_string", "Bankr. S.D. Florida", "Bankr. S.D. Fla.", "Florida spelled out"),
    ("ct-oknb", "oknb", "court_string", "Bankr. N.D. Okla", "Bankr. N.D. Okla.", "missing period after Okla"),
    # Bankruptcy appellate panels: "9th Cir. BAP" -> "B.A.P. 9th Cir."
    ("ct-bap1", "bap1", "court_bap", "1st Cir. BAP", "B.A.P. 1st Cir.", "BAP order"),
    ("ct-bap2", "bap2", "court_bap", "2d Cir. BAP", "B.A.P. 2d Cir.", "BAP order"),
    ("ct-bap6", "bap6", "court_bap", "6th Cir. BAP", "B.A.P. 6th Cir.", "BAP order"),
    ("ct-bap8", "bap8", "court_bap", "8th Cir. BAP", "B.A.P. 8th Cir.", "BAP order"),
    ("ct-bap9", "bap9", "court_bap", "9th Cir. BAP", "B.A.P. 9th Cir.", "BAP order"),
    ("ct-bap10", "bap10", "court_bap", "10th Cir. BAP", "B.A.P. 10th Cir.", "BAP order"),
    # $byId: the string is only wrong on this court id.
    ("ct-nmid", "nmid", "court_string", "N. Mar. I.", "D. N. Mar. I.", "district court stored as the supreme court"),
    ("ct-nmib", "nmib", "court_string", "Bankr. N. Mar. I.", "Bankr. D. N. Mar. I.", "missing D."),
    ("ct-ianb", "ianb", "court_string", "Bankr. D. Iowa", "Bankr. N.D. Iowa", "N.D. Iowa bankruptcy stored as D. Iowa"),
    # Cal. Ct. App. 1st..6th -> "Cal. Ct. App." The district in the string is not the Bluebook form.
    # calctapp5d's "5th" is the Cal.App.5th reporter series.
    ("ct-cal1", "calctapp1d", "court_cal", "Cal. Ct. App. 1st", "Cal. Ct. App.", "district written into the court"),
    ("ct-cal2", "calctapp2d", "court_cal", "Cal. Ct. App. 2nd", "Cal. Ct. App.", "2nd, and district written into the court"),
    ("ct-cal3", "calctapp3d", "court_cal", "Cal. Ct. App. 3rd", "Cal. Ct. App.", "3rd, and district written into the court"),
    ("ct-cal4", "calctapp4d", "court_cal", "Cal. Ct. App. 4th", "Cal. Ct. App.", "district written into the court"),
    ("ct-cal5", "calctapp5d", "court_cal", "Cal. Ct. App. 5th", "Cal. Ct. App.", "5th is the reporter series, not a district"),
    ("ct-cal6", "calctapp6d", "court_cal", "Cal. Ct. App. 6th", "Cal. Ct. App.", "district written into the court"),
    # Ordinal rule: (\d)(?:nd|rd) -> $1d. One federal example and one of each state pattern.
    ("ct-ca3", "ca3", "court_ordinal", "3rd Cir.", "3d Cir.", "3rd where the form is 3d"),
    ("ct-mich2", "micirct2", "court_ordinal", "Mich. Cir. Ct., 2nd Cir.", "Mich. Cir. Ct., 2d Cir.", "2nd"),
    ("ct-mich3", "micirct3", "court_ordinal", "Mich. Cir. Ct., 3rd Cir.", "Mich. Cir. Ct., 3d Cir.", "3rd"),
    # v1.0 gold was "Oh. Ct. App. 2d Dist. Champaign"; "Oh." is not an abbreviation. Bluebook T1 is "Ohio Ct. App.".
    ("ct-oh2", "ohctapp2champai", "court_ordinal", "Oh. Ct. App. 2nd Dist. Champaign", "Ohio Ct. App. 2d Dist.", "2nd, and Oh. for Ohio"),
    ("ct-flacir2", "flacirct2", "court_ordinal", "2nd", "2d", "Florida circuit stored as 2nd"),
    ("ct-flacir3", "flacirct3", "court_ordinal", "3rd", "3d", "Florida circuit stored as 3rd"),
    # One court id for every department. The string names no department.
    ("ct-nyappdiv", "nyappdiv", "court_generic", "N.Y. App. Div.", "N.Y. App. Div. 2d Dep't", "no department"),
    ("ct-illappct", "illappct", "court_generic", "Ill. App. Ct.", "Ill. App. Ct. 1st Dist.", "no district"),
    ("ct-ohioctapp", "ohioctapp", "court_generic", "Ohio Ct. App.", "Ohio Ct. App. 10th Dist.", "no district"),
    ("ct-texapp", "texapp", "court_generic", "Tex. App.", "Tex. App.—Houston [14th Dist.]", "no city"),
    # fladistctapp1..6 spell "Nth Dist." The builder collapses that and emits Fla. Nth DCA.
    ("ct-fla1", "fladistctapp1", "court_fl", "Fla. Dist. Ct. App. 1st Dist.", "Fla. 1st DCA", "numbered DCA form"),
    ("ct-fla2", "fladistctapp2", "court_fl", "Fla. Dist. Ct. App. 2d Dist.", "Fla. 2d DCA", "numbered DCA form"),
    ("ct-fla3", "fladistctapp3", "court_fl", "Fla. Dist. Ct. App. 3d Dist.", "Fla. 3d DCA", "numbered DCA form"),
    ("ct-fla4", "fladistctapp4", "court_fl", "Fla. Dist. Ct. App. 4th Dist.", "Fla. 4th DCA", "numbered DCA form"),
    ("ct-fla5", "fladistctapp5", "court_fl", "Fla. Dist. Ct. App. 5th Dist.", "Fla. 5th DCA", "numbered DCA form"),
    ("ct-fla6", "fladistctapp6", "court_fl", "Fla. Dist. Ct. App. 6th Dist.", "Fla. 6th DCA", "numbered DCA form"),
    # Empty citation_string. The builder fills five of these; vacc is the control that is already filled.
    ("ct-vacc", "vacc", "court_empty", "", "Va. Cir. Ct.", "local courts row is already Va. Cir. Ct.; live citation_string is still empty"),
    ("ct-vachan", "vachanct", "court_empty", "", "Va. Ch. Ct.", "empty citation_string"),
    ("ct-ohioco", "ohiocountyct", "court_empty", "", "Ohio Cnty. Ct.", "empty citation_string"),
    ("ct-ard", "ard", "court_empty", "", "D. Ark.", "empty citation_string"),
    ("ct-okd", "okd", "court_empty", "", "D. Okla.", "empty citation_string"),
    # Trailing space. trim() in the builder is what removes it.
    ("ct-vt", "vtsuperct", "court_space", "Vt. Super. Ct. ", "Vt. Super. Ct.", "trailing space"),
]


# A second accepted answer. The first entry is the builder's form, the rest are
# forms the Bluebook also allows (or prefers) for the same court.
ALSO_RIGHT = {
    # 10.4(b): the plain form is the Bluebook answer; the department form is local practice.
    "ct-nyappdiv": ["N.Y. App. Div."],
    "ct-illappct": ["Ill. App. Ct."],
    "ct-ohioctapp": ["Ohio Ct. App."],
    "ct-texapp": ["Tex. App."],
    "ct-oh2": ["Ohio Ct. App."],
    # Both spacings of the Northern Mariana Islands district court are in use.
    "ct-nmid": ["D.N. Mar. I."],
    "ct-nmib": ["Bankr. D.N. Mar. I."],
}

# Extra wrong forms for the ANSWER line (the stored string is always one).
ALSO_WRONG = {
    "ct-oh2": ["Oh. Ct. App.", "2nd"],
}


def main():
    with open(OUT, "w") as f:
        for iid, court, klass, wrong, right, why in ROWS:
            gold = {
                "wrong": wrong,
                "right": right,
                "why": why,
                "source": "live_xeric_bluebook.php bluebookCourtCite / bluebookCourtCiteForCase",
            }
            if iid in ALSO_RIGHT:
                gold["any_right"] = [right] + ALSO_RIGHT[iid]
            if iid in ALSO_WRONG:
                gold["also_wrong"] = ALSO_WRONG[iid]
            row = {
                "id": iid,
                "class": klass,
                "tool": "court",
                "court_id": court,
                "gold": gold,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(ROWS)} {OUT}")


if __name__ == "__main__":
    main()
