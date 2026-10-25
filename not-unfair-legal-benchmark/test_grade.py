# Unit tests for grade.py (v1.1). Plain asserts.
# run: python3 test_grade.py   or   python3 -m pytest test_grade.py
# Each test names the v1.0 behaviour it replaces ("before") and what v1.1 does.
import json
import os

import grade

HERE = os.path.dirname(os.path.abspath(__file__))


def passes(answer, gold):
    return grade.grade(answer, gold)[0]


# --- ANSWER line -----------------------------------------------------------

def test_wrong_form_in_explanation_is_allowed():
    # before: "Fla. 1st DCA, not Fla. Dist. Ct. App." missed on `wrong` anywhere in the answer.
    gold = {"right": ["Fla. 1st DCA"], "wrong": ["Fla. Dist. Ct. App."]}
    assert passes("The court is Fla. 1st DCA, not Fla. Dist. Ct. App.\nANSWER: Frederick v. United Airlines, 688 So. 2d 412 (Fla. 1st DCA 1997)", gold)
    # after: the bad form on the ANSWER line still fails.
    assert not passes("ANSWER: Frederick v. United Airlines, 688 So. 2d 412 (Fla. Dist. Ct. App. 1997); also Fla. 1st DCA", gold)


def test_vendor_cite_named_only_to_reject_it():
    # before: "do not use 2003 WL 23353478" failed forbid_vendor.
    gold = {"any_right": ["216 F.R.D. 481"], "forbid_vendor": True}
    assert passes("Do not use 2003 WL 23353478; the reporter cite exists.\nANSWER: Pitman v. Brinker Int'l, Inc., 216 F.R.D. 481 (D. Ariz. 2003)", gold)
    assert not passes("ANSWER: Pitman v. Brinker Int'l, Inc., 216 F.R.D. 481, 2003 WL 23353478 (D. Ariz. 2003)", gold)


def test_absent_phrase_in_explanation_is_allowed():
    # before: op-01 missed because "I have not found an overruling" contains "not found".
    gold = {"right": ["58 Misc. 3d 300"], "absent": ["not found", "does not exist"]}
    assert passes("I have not found an overruling decision.\nANSWER: 90 Elizabeth Apt. LLC v. Eng, 58 Misc. 3d 300 (App. Term 2017)", gold)
    assert not passes("ANSWER: 58 Misc. 3d 300 does not exist", gold)


def test_no_answer_line_falls_back_to_last_line_and_flags_it():
    gold = {"right": ["3d Cir."], "wrong": ["3rd Cir."]}
    r = grade.grade_item("The form is 3d Cir.\n3rd Cir. is wrong", gold)
    assert r["no_answer_line"] is True
    assert r["passed"] is False  # last line carries the wrong form
    r = grade.grade_item("3rd Cir. is wrong.\nThe form is 3d Cir.", gold)
    assert r["no_answer_line"] is True and r["passed"] is True
    r = grade.grade_item("3rd Cir. is wrong.\nANSWER: 3d Cir.", gold)
    assert r["no_answer_line"] is False and r["passed"] is True


def test_answer_line_markdown_and_case():
    gold = {"right": ["B.A.P. 9th Cir."], "wrong": ["9th Cir. BAP"]}
    assert passes("9th Cir. BAP is stored.\n**Answer:** B.A.P. 9th Cir.", gold)
    assert passes("9th Cir. BAP is stored.\nanswer: B.A.P. 9th Cir.", gold)


# --- history any_of --------------------------------------------------------

def test_history_supreme_court_alone_no_longer_passes():
    # before: any_of held "Supreme Court" and "certiorari", so "this is a Supreme Court opinion" passed.
    rows = {r["id"]: r for r in load_tasks()}
    g = rows["h-110"]["gold"]
    assert "Supreme Court" not in g["any_of"] and "certiorari" not in g["any_of"]
    assert not passes("ANSWER: this is a Supreme Court opinion", g)
    assert passes("ANSWER: 110 S. Ct. 1128 is an orders page: cert. denied in Oxley v. City of Tulsa, 794 P.2d 742", g)


def test_h421_any_one_name():
    # before: all five names were required for a bare "421 U.S. 901".
    rows = {r["id"]: r for r in load_tasks()}
    g = rows["h-421"]["gold"]
    assert passes("ANSWER: 421 U.S. 901 is an orders page; Roemer v. Board of Public Works was dismissed for want of a substantial federal question", g)


# --- treatment verdict on the ANSWER line, never negated -------------------

def test_negated_treatment_fails():
    # before: "has not been overruled" passed any_of "overruled".
    gold = {"any_of": ["overruled", "abrogated"], "verdict_line": True}
    assert not passes("ANSWER: Real v. Shannon, 600 F.3d 302, has not been overruled", gold)
    assert not passes("ANSWER: Real v. Shannon, 600 F.3d 302; never overruled or abrogated", gold)
    assert passes("ANSWER: Chevron, 467 U.S. 837, overruled by Loper Bright Enterprises v. Raimondo (2024)", gold)
    assert passes("ANSWER: abrogated by Reynolds v. United States, not overruled outright", gold)


def test_treatment_verdict_must_be_on_answer_line():
    gold = {"any_of": ["overruled"], "verdict_line": True}
    assert not passes("Chevron was overruled by Loper Bright.\nANSWER: Chevron U.S.A. Inc. v. NRDC, 467 U.S. 837 (1984)", gold)
    assert passes("Chevron was overruled by Loper Bright.\nANSWER: 467 U.S. 837, overruled", gold)


def test_quotation_any_of_reads_whole_answer():
    gold = {"any_of": ["garbled", "ocr"]}
    assert passes("The text is garbled OCR.\nANSWER: not safe to quote", gold)
    assert not passes("The text is not garbled.\nANSWER: reliable", gold)


# --- normalisation ---------------------------------------------------------

def test_dashes_normalise():
    # before: "Tex. App.—Houston" needed the exact em dash.
    gold = {"any_right": ["Tex. App.—Houston [14th Dist.]", "Tex. App."]}
    assert passes("ANSWER: Tex. App.-Houston [14th Dist.]", gold)
    assert passes("ANSWER: Tex. App. – Houston [14th Dist.]", gold)
    assert passes("ANSWER: Tex. App. -- Houston [14th Dist.]", gold)


def test_apostrophes_normalise():
    gold = {"right": ["Ct. Int'l Trade"]}
    assert passes("ANSWER: Ct. Int’l Trade", gold)
    assert passes("ANSWER: Ct. Int`l Trade", gold)


def test_whitespace_collapses():
    gold = {"right": ["Bankr. D. Colo."]}
    assert passes("ANSWER: Bankr.  D. Colo.", gold)


def test_mariana_islands_both_spacings():
    # The two spacings are both accepted on the N. Mar. I. items (any_right), not by
    # a global rule: a global space-normalisation would make D. N.Y. equal D.N.Y. and
    # kill the items that test that very space.
    rows = {r["id"]: r for r in load_tasks()}
    g = rows["ct-nmid"]["gold"]
    assert passes("ANSWER: D. N. Mar. I.", g)
    assert passes("ANSWER: D.N. Mar. I.", g)
    g = rows["ct-nyd"]["gold"]
    assert passes("ANSWER: D.N.Y.", g)
    assert not passes("ANSWER: D. N.Y.", g)


# --- passage builder -------------------------------------------------------

def test_no_double_period_after_abbreviation():
    # before: "Correct this court abbreviation to Bluebook form: 3rd Cir.."
    for r in load_tasks():
        assert ".." not in r["text"], r["id"] + ": " + r["text"]


# --- gold shape ------------------------------------------------------------

def test_captions_take_surnames():
    rows = {r["id"]: r for r in load_tasks()}
    assert passes("ANSWER: Doe v. Blum", rows["cap-svc-01"]["gold"])
    assert not passes("ANSWER: Medicare&medicaid Gu 33,639 Jane Doe v. Barbara Blum", rows["cap-svc-01"]["gold"])
    assert passes("ANSWER: Corp. Sys. Res. v. Wash. Metro. Area Transit Auth.", rows["cap-list-02"]["gold"])


def test_district_form_items_accept_plain_bluebook_form():
    rows = {r["id"]: r for r in load_tasks()}
    assert passes("ANSWER: Ill. App. Ct.", rows["ct-illappct"]["gold"])
    assert passes("ANSWER: Ill. App. Ct. 1st Dist.", rows["ct-illappct"]["gold"])
    assert passes("ANSWER: Ohio Ct. App.", rows["ct-oh2"]["gold"])
    assert not passes("ANSWER: Oh. Ct. App. 2d Dist.", rows["ct-oh2"]["gold"])


def test_ordered_published_items_take_the_published_cite():
    rows = {r["id"]: r for r in load_tasks()}
    g = rows["c4b-05"]["gold"]
    assert passes("83 F. App'x 274 was ordered published.\nANSWER: Umbach v. Commissioner, 357 F.3d 1108 (10th Cir. 2004)", g)
    assert not passes("ANSWER: unpublished", g)


def test_coverage_items_need_a_fact_not_in_the_passage():
    rows = {r["id"]: r for r in load_tasks()}
    g = rows["op-02"]["gold"]
    assert not passes("ANSWER: Meuers Law Firm v. Reasor's, 796 F. App'x 472", g)
    assert passes("ANSWER: Meuers Law Firm v. Reasor's, 796 F. App'x 472 (10th Cir. 2019)", g)


def test_controls_pass_a_plain_confirmation_and_fail_a_false_correction():
    rows = {r["id"]: r for r in load_tasks()}
    g = rows["co-01"]["gold"]
    assert passes("ANSWER: Erie R.R. Co. v. Tompkins, 304 U.S. 64 (1938), correct as written", g)
    assert not passes("ANSWER: 304 U.S. 64 is a misprint for 304 U.S. 65", g)
    assert not passes("ANSWER: 304 U.S. 64 does not exist", g)


def test_every_task_has_evidence_and_passes_self_check():
    for r in load_tasks():
        assert r.get("evidence"), r["id"] + " has no evidence"
        ok, why = grade.self_check(r)
        assert ok, r["id"] + ": " + why


def load_tasks():
    path = os.path.join(HERE, "items", "tasks.jsonl")
    return [json.loads(line) for line in open(path) if line.strip()]


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("ok  ", name)
        except AssertionError as e:
            failed += 1
            print("FAIL", name, "-", e)
    print(f"{len(tests) - failed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
