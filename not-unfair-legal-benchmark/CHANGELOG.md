# Changelog

## v1.3 — 2026-11-08

292 passages (v1.2 had 250), if wave 3 is accepted as staged.

### Gold: added — decision years (new class `date`, 20 traps)

Built by `build_wave3.py` from the 2026-11-08 decision-year corrections (DATE176). In each, the CourtListener
corpus stores a year more than five years outside the year span of the reporter volume (a 1950s A.2d volume
carrying a "2001" decision). Citing courts print the right year, and none print the stored one. Ids
`dt-<court>-<n>`. Two shapes:

- shape (i): the passage gives the case with the true year. CourtListener returns FOUND with its stored date. The
  answer is correct as written; the ANSWER line must carry the true year and not the stored one.
- shape (ii): the passage gives CourtListener's stored year. CourtListener returns FOUND and confirms it. The
  ANSWER line must carry the true year and not the stored one.

Only the year was corrected. The month and day CourtListener holds are unverified, so no gold string contains
them. 10 Maryland Court of Appeals cases (A.2d, 1950-1956) and 10 from other courts: Minn. ×2, Mich., Tex., R.I.,
S.D.N.Y., Pa., Ill. App. Ct., 5th Cir., Ark.; decided 1914-1968.

Evidence: every item quotes two to four citing opinions that name the case and print the year (found with the
syfert.com MCP search_cases, 2026-11-08). It also records the volume's year span, CourtListener's stored date, and
how many citing opinions predate the stored year. Nine rows were dropped for thin evidence or a second cluster at
the cite. The raw CourtListener arm passed one candidate (its LEXIS parallel cite carries the true year), which was
dropped.

### Gold: added — regional reporter numbers, second batch (16 traps)

Same method as v1.2's `rg-*` items (`build_regional.py` code), from RESCORE166 `fixA2b` and `fixC2`. Ids `rg3-*`.
12 class A and 4 class C, 9 shape (i) and 7 shape (ii), in 11 reporters. The raw CourtListener arm passed none. One
row was reviewed out (Sweeney v. Union State Bank: the citers' number may be a separate opinion).

### Controls: added (6)

`dt-co-1..6`: correct cites printed with their correct year, from the same volumes as the date traps (3 Md. A.2d, Pa.
A.2d, Minn. N.W.2d, U.S.). They are not in any fix ledger or the date-suspect list.

### Grader

No change. Date items use `any_of` + `verdict_line` for the year.

### Limitations

- Half the date class is one court in one decade (Maryland 1950s), because 247 of the 286 fixes are there.
- Shape (i) date items, like controls, are passed by an answer that repeats the passage.
- One record-format fix in CourtListener (re-dating these clusters) would flip the date class.

### Review calls (2026-11-08)

- Shape (i) date passages already contain the right year, so repeating the passage passes, as with the controls; kept.
- The date year is graded on the ANSWER line (the treatment items' mechanism); kept.
- `dt-pa-1` (Wallace v. Wallace) dropped at the CourtListener step: its reply lists `1952 Pa. LEXIS 433`, which carries the
  true year. Sweeney v. Union State Bank reviewed out after that step: citers print another volume and page under another
  caption, possibly a separate opinion.
- Noted, not graded: CourtListener flags Bluebook-abbreviated case names as possible hallucinations, controls included,
  which could push a model using it toward a false rejection.

### Scores

Raw Syfert MCP arm on the 42 new items, grader v1.2 rules (`run_syfert.py items/wave3.jsonl`):

| run | server state | date (20) | regional (16) | controls (6) | total (42) |
|---|---|---|---|---|---|
| `results/20261108-syfert-raw-wave3-pre` | driver 5cd5a699 / lib ea067535 | 10 | 16 | 6 | 32 |
| `results/20261108-syfert-raw-wave3` | + REL179: a year_mismatch correction carries a paste-ready cite | 19 | 16 | 6 | 41 |

The first run's 10 date misses: the tool flagged every wrong year and named the decision year, but its correction had no
replacement, so the rendered ANSWER line repeated the wrong year. The remaining miss (`dt-md-6`, 119 A.2d) is the tool
declining to offer a full corrected cite in a volume whose own dates are mixed; it still names the right year. As with
the regional class, Syfert's index was corrected from the evidence the gold rests on, so this arm checks that the
corrections reach the tool; it is not an independent comparison.

## v1.2 — 2026-11-07

250 passages (v1.1 had 202). The 202 v1.1 passages and their gold are unchanged (a rebuild of v1.1 is byte-identical).

### Gold: added — regional reporter numbers (41 traps, 7 controls)

Built by `build_regional.py` from the 2026-11-07 regional-reporter corrections (RESCORE166 class A and class C,
FIX154). In each, the CourtListener corpus holds a regional reporter number for the case that citing courts do not
print; the gold is the number they do print. Ids `rg-<reporter>-a*` (class A: no other case at the printed
number) and `rg-<reporter>-c*` (class C: the old number is the first page of a different case, named in the gold
note). Two shapes:

- shape (i): the passage gives the case with the printed number. CourtListener returns NOT FOUND. Graded like a
  coverage item: the printed number, plus the decision date or the court, with no rejection on the ANSWER line and
  not the old number.
- shape (ii): the passage gives the old CourtListener number. CourtListener returns FOUND (class A) or AMBIGUOUS
  between the case and the other case at that page (class C). The gold is the printed number; the old number may
  not be on the ANSWER line.

14 reporters (S.E., S.E.2d, N.W., N.W.2d, N.E., N.E.2d, P., P.2d, A., A.2d, So., So. 2d, S.W., S.W.2d), 2-3 traps
each, decisions 1892-2014; 28 class A, 13 class C; 21 shape (i), 20 shape (ii). Seven controls `rg-co-*` (one per
first- or second-series regional reporter, 1923-1997), ordinary correct cites not in any fix ledger.

Evidence: every item quotes two to four citing opinions (cluster id, name, date, snippet printing the number with
the case name), found with the syfert.com MCP search_cases on 2026-11-07; the decision year is checked against the
reporter volume. The corpus behind syfert.com is CourtListener-derived, so the gold rests on the citing courts'
printed text, not on that index. Seven rows were dropped for thin evidence (listed in
`results/20261107-regional-wave/drops.jsonl`). The raw CourtListener arm passed none of the trap candidates, so none
was dropped for that; the arm's replies are in `results/20261107-regional-wave/cl/`.

### Limitations

- Most of the wave (27 of 41) is a wrong page in the right volume; 14 are the right page in the wrong volume.
- First-series reporters dominate the eras (24 of 41 decisions are before 1940), because that is where the
  corrections are.
- One record-format fix in CourtListener (re-attaching the printed numbers) would flip the whole class.

### Review calls (2026-11-07)

- `rg-so-a1` (Woodson v. State, 54 So. 181) reviewed out after the CourtListener step: CourtListener also places a
  second case (Western Union Tel. Co. v. Stokes) at the old number, so the item tested two things at once. The
  stratum's spare `rg-so-a3` (Faulk v. Calloway, 20 So. 504 → 26 So. 504) stands in. Recorded in `drops.jsonl`
  (stage `review`).
- Class C shape (ii): CourtListener answers AMBIGUOUS and names both cases. The gold still requires the printed
  number; naming both cases leaves the brief citing a number that belongs to someone else.
- Shape (i): the court's full name ("Supreme Court of Georgia") counts as naming the court. The bare state ("Ga.")
  does not, because it is also a substring of the wrong court ("Ga. Ct. App.").

### Grader: the echo hole (v1.2 rule)

`grade_item(answer, gold, passage)` now takes the passage. The passage text is removed from every line above the
ANSWER line before the `right` / `any_right` / `any_of` search, because renderers echo the tool call, which repeats
the passage: under v1.1 an item whose passage already held the gold string passed with no answer at all (found in
the 2026-11-03 kaos-citations run). The ANSWER line itself is kept whole, so an answer that rightly repeats the
cite as written (every control) still counts. `no answer from the tool` on the ANSWER line is a miss.
`grade_answers.py` and `score_saved.py` pass the passage. Called without a passage, grading is as in v1.1 except
for the no-answer rule. Three tests added (`test_grade.py`, 24 pass).

Re-grades of saved runs on the 202 v1.1 passages under the v1.2 grader (no arm re-run):

| run | v1.1 grader | v1.2 grader |
|---|---|---|
| `results/20261027-syfert-raw4` | 202 | 199 (c10-02/03/04: the tool gave no answer on a quotation item) |
| `results/20261103-kaos-raw` | 39 | 27 (controls 22 of 24) |

## v1.1 — 2026-10-25

202 passages (v1.0 had 187). Code and data only: no arm was re-run for this
release. The scores below are re-grades of the transcripts saved from the
2026-10-22 runs; v1.1 scores from fresh runs are pending.

### Why

An independent review of the v1.0 set (2026-10-24) found gold that was wrong or
contradicted the prompt, a string matcher that failed answers for naming the bad
form while correcting it, and no control items. Every change below cites the
item id, the old gold, the new gold, and the reason. Every item that stayed was
checked on 2026-10-25 against the public corpus behind syfert.com (the live MCP
tools check_citation, check_brief, find_case, get_treatment) and carries a new
`evidence` field with the cluster id of the case the gold rests on. Court-form
items cite the Bluebook rule instead.

### Gold: dropped (13)

| id | passage | v1.0 gold | why dropped |
|---|---|---|---|
| c4-01 | Citigroup Global Markets v. VCG, 598 F.3d 30 | overruled | green on the live treatment tool (391 positive citing events, 0 negative). The red came from a flag-database row where the citing opinion's own "we overrule" spilled onto a string cite. |
| c4-02 | Real v. Shannon, 600 F.3d 302 | overruled | same; green (65/0). Already known as a false red before the review. |
| c4-03 | United States v. Brown, 595 F.3d 498 | overruled | same; green (76/0). |
| c4-05 | United States v. Bell, 598 F.3d 366 | overruled | same; green (11/0). |
| c4-07 | United States v. Caro, 597 F.3d 608 | overruled | green; the only negative signals are two "but see" cites in unpublished Idaho opinions. |
| c4-08 | United States v. Corner, 598 F.3d 411 | overruled | green (167/0). Corner overruled other cases; its own text was the spill. |
| c1-01 | Hawai'i State Teachers Ass'n v. University Laboratory School, 467 P.3d 346 | the cite is real | a 2013 opinion in a 2020 volume of P.3d. The only provenance is an aggregator volume listing. Not verifiable against the reporter. |
| c1-02 | Haygood v. State, 308 So. 3d 85 | the cite is real | 308 So. 3d 85 is a table page: four Fla. 2d DCA dispositions share it in the corpus (Price, Haygood, Najdzion, Armstrong), aggregator-only provenance. |
| c1-04 | Com. v. Moffatt, 227 A.3d 416 | the cite is real | a Pa. Super. Ct. table page shared by five unpublished memoranda (Stapp, Moffatt, Jackson, Poole, Fitzpatrick). |
| c1-07 | Commonwealth v. Terrell, 238 A.3d 333 | the cite is real | a Pa. Supreme Court allocatur table page shared by four cases. |
| c6-10 | Das v. American Airlines, 2020 WL 364264 | find the case | the Westlaw number cannot be verified in the corpus (a suggestion from two citing opinions, not a confirmed alias). |
| c6-13 | Vape Central Group v. FDA, 2025 WL 637416 | find the case | the Westlaw number rests on user claims only. |
| ct-hl | HL (House of Lords) | H.L. | a UK court; the T2 form is arguable. Not a US caselaw item. |

### Gold: changed (kept with new gold)

| id(s) | v1.0 gold | v1.1 gold | why |
|---|---|---|---|
| cap-svc-01..08 | the stored given names ("Jane Doe v. Barbara Blum", "Rose Mayburg", "Donald M. Kass", ...) | surnames ("Doe", "Blum"; "Mayburg"; "Kass"; ...). `wrong` also rejects "soc.sec.rep.ser." on the ANSWER line. | Bluebook 10.2.1(g) omits given names and initials; "Doe v. Blum" was a correct answer that v1.0 failed. |
| cap-list-02 | "Corporate Systems Resources" | any of "Corporate Systems Resources", "Corp. Sys. Res", "Corporate Sys. Res" | T6 abbreviates the words; both forms are right. |
| cap-list-05 | "Associated Builders and Contractors" | "Associated Builders" | "and" becomes "&" in a Bluebook case name. |
| cap-list-06 | "American Immigration Council" | any of the full name, "Am. Immigration Council", "Am. Immigr. Council" | T6 abbreviation. |
| cap-front-01 | "Ex parte" | "Ex parte" and "Hartfield" | the opinion's caption is Ex parte Jerry Hartfield; the v1.0 string alone was too weak. |
| cap-front-02 | "Eugenia Arpon" | any of "Arpon", "Vda de Samala", "Vda. de Samala", "Viuda de Samala" | 10.2.1(g) again: the given name is not the answer. The plaintiff is Eugenia Arpon Vda. de Samala; CourtListener stores "de Samala v. United States". The point of the item is the cut-off front of the caption. |
| ct-nyappdiv, ct-illappct, ct-ohioctapp, ct-texapp | the department/district form only ("Ill. App. Ct. 1st Dist."), plain form marked wrong | either form accepted ("Ill. App. Ct. 1st Dist." or "Ill. App. Ct."); nothing marked wrong | Bluebook 10.4(b): do not add the department or district of an intermediate state court unless it matters. v1.0 contradicted itself (ct-cal* forbade the district, these four required it). |
| ct-oh2 | "Oh. Ct. App. 2d Dist. Champaign" | "Ohio Ct. App. 2d Dist." or "Ohio Ct. App."; wrong: "Oh. Ct. App.", "2nd" | "Oh." is not an abbreviation anywhere. Bluebook T1 is "Ohio Ct. App.". |
| ct-nmid, ct-nmib | "D. N. Mar. I." / "Bankr. D. N. Mar. I." | also "D.N. Mar. I." / "Bankr. D.N. Mar. I." | both spacings are in use. Done per item, not by a global space rule: a global rule would make "D. N.Y." equal "D.N.Y." and kill the items that test that space (ct-nyd, ct-wvnd, ct-wvsd, ct-wvnb, ct-wvsb, ct-wvad, ct-cob). |
| ct-fla1..6, dca-*, flw-* (27 items) | unchanged: "Fla. 1st DCA" ... "Fla. 6th DCA" | unchanged | the PROMPT now says so: "For a Florida district court of appeal, use the form the Florida courts prescribe in Fla. R. App. P. 9.800 ... Do not write Fla. Dist. Ct. App." The dca-* and flw-* passages repeat it. The gold was planted on purpose; the instruction was the gap. |
| c4b-05, c4b-06, c4b-07 | "unpublished" | the published cite (357 F.3d 1108; 360 F.3d 1155; 367 F.3d 1215) or "ordered published" / "later published" / "subsequently published". Passage now ends "Give the current citation and publication status." | the Tenth Circuit later ordered all three Federal Appendix opinions published. "Unpublished" is not the right answer for a published decision. c4b-07 (Ustyan) was found in the v1.1 audit; the review had flagged 05 and 06. |
| c4b-01..04, c4b-08 | any of the unpublished words anywhere | same words, on the ANSWER line, not negated | grader rule (below). Evidence: Federal Appendix cite, 10th Cir. R. 32.1, no published parallel in the corpus. |
| c4-04, c4-06, p05-treatment | any of overruled / receded / abrogated / no longer good law anywhere | same (plus superseded, not good law, disapproved), on the ANSWER line, not negated | grader rule. Evidence: Shenandoah abrogated by Reynolds v. United States (2012); Maggi/Antelope overruled in part by United States v. Zepeda (9th Cir. 2015) (en banc); Chevron overruled by Loper Bright (2024). |
| h-421 | all five names (Wicks, Harris, Roemer, Rivers, Dickinson) | any one of them | one page, five dismissals; a bare "421 U.S. 901" cannot ask for all five. |
| h-67, h-68a, h-68b, h-110, h-114, h-ord-01..09 | any of the cert./orders words, including "Supreme Court" and "certiorari" alone; no right string | the cert./orders words without "Supreme Court" and "certiorari"; plus any one case on the page (names read from the saved CourtListener reply) or, where the page is wrongly attached to a lower-court opinion, that opinion's reporter cite (173 P.2d 235, 192 P.2d 289, 67 F. Supp. 326, 794 P.2d 742, 102 F.3d 671) | "this is a Supreme Court opinion" passed an orders-page item. |
| h-102 | five short names | the same, plus the full names on the page and 102 F.3d 671 | as above. |
| c1-03, c1-05, c1-06, c1-08, op-01..08 | the cite as printed, with rejection phrases absent | the cite, and one fact not in the passage: the docket number, the decision date, or the court (circuit or numbered Florida district) | an answer that echoed the passage passed v1.0. |
| c6-07, c6-08, c6-09, c6-11, c6-12 | the case name as printed | the surname, and the docket number, court, or decision date | same. |
| c6-02 | "11 Tex. Ct. App. 114" | also "11 Tex. App. 114" | both abbreviations of the Texas Court of Appeals Reports are used. |
| c6-03 | "17 C.M.A. 147", "17 USCMA 147", "37 C.M.R. 411" | also "17 U.S.C.M.A. 147" | spelling variant. |
| p03-name-collapse | any of five mismatch phrases | plus "not Smith", "no case named Smith", "mismatch" | wording variants of the same verdict. |

### Gold: added

- `t-bowers` Bowers v. Hardwick, 478 U.S. 186 (overruled by Lawrence v. Texas, 2003); `t-quill` Quill Corp. v. North Dakota, 504 U.S. 298 (overruled by South Dakota v. Wayfair, 2018); `t-abood` Abood v. Detroit Board of Education, 431 U.S. 209 (overruled by Janus, 2018); `t-azzarello` Azzarello v. Black Bros. Co., 391 A.2d 1020 (Pa. 1978) (overruled by Tincher v. Omega Flex, 2014). Four treatment items across reporters and decades, each red on the live treatment tool with the overruling case recorded in `evidence`. The three Supreme Court ones are tagged `bare_model_answerable`.
- `co-01` .. `co-24`: 24 control items (`kind: control`, class `control`), built by `build_controls.py`. Ordinary, correct citations; the right answer is the citation itself, correct as written. Twelve are casebook cases a bare model knows (tagged `bare_model_answerable`); twelve are ordinary reported cases nobody memorises (bankruptcy, 1890s state reports, 2009-2010 circuit cases), so an arm cannot tell a control from a trap by fame. Controls are reported on their own row so a false-positive rate can be read off the table.

### Tags

- `bare_model_answerable: true` on pin-02..14, p04-interior, c10-01..06, p05-treatment, t-bowers, t-quill, t-abood and the twelve casebook controls. They stay in the set as sanity rows; they are not CourtListener traps.
- `kind: control` on the 24 controls.
- `evidence` on every item.
- `version: "1.1"` on every item; `VERSION` file at the root.

### Grader (grade.py)

- The PROMPT asks for a final line beginning `ANSWER:` that holds only the corrected citation, court form, case name or verdict. `wrong`, `absent` and `forbid_vendor` are now read on that line only, so "Fla. 1st DCA, not Fla. Dist. Ct. App." and "do not use 2003 WL 23353478" pass. `right`, `any_right` and `any_of` still read the whole answer. When there is no ANSWER line the last non-empty line is graded and the per-item result carries `no_answer_line: true` (`grade.grade_item`; `grade.grade` keeps the old `(passed, reason)` shape).
- Treatment items (`verdict_line: true`) need the verdict word on the ANSWER line, and a negated verdict does not count: "has not been overruled" no longer passes "overruled".
- `norm()` maps every dash (– — -- −) to one hyphen and removes the spaces around it ("Tex. App. — Houston" equals "Tex. App.—Houston"), maps curly and back-tick apostrophes to one, collapses whitespace and non-breaking spaces. It does not remove the space between abbreviation tokens (see ct-nmid above for why).
- History `any_of` no longer contains "Supreme Court" or "certiorari"; the cert./orders family stays and gains "order list", "dismissed for want" and spelling variants.
- The passage builder no longer prints a double period after an abbreviation ("3rd Cir.." is now "3rd Cir.").
- `REJECT` gains "could not find", "fabricated", "hallucinat", "not a section", "no such section", "no such title".
- `test_grade.py`: 21 unit tests with before/after cases for each change (`python3 test_grade.py` or `python3 -m pytest`).
- `grade_answers.py` (new): grades a jsonl file of `{"id", "answer"}` rows against the set and prints the class table with controls on their own row.

### Re-grade of the saved transcripts (not new runs)

The 2026-10-22 transcripts were graded again with the v1.1 grader against the v1.1 set. Only the 174 v1.1 items that existed in v1.0 have a transcript; the 28 new items (24 controls, 4 treatment) have none and are not counted. None of the saved transcripts has an ANSWER: line (the v1.0 prompt did not ask for one), so every one was graded on its last non-empty line. That matters for the vendor class: the saved Grok answers end by listing the parallel Westlaw numbers, which the v1.1 rule reads as the ANSWER line. A fresh run under the v1.1 prompt is the real v1.1 number.

| arm | v1.0 grader, v1.0 set (187) | v1.1 grader, v1.1 set (174 graded) |
|---|---:|---:|
| raw CourtListener analyze_citations bodies (server 9386476) | 0 / 187 | 24 / 174 |
| Grok 4.7 + CourtListener MCP + web | 112 / 187 (59.9%) | 121 / 174 (69.5%) |
| Grok 4.7 + Syfert MCP + web | 123 / 187 (65.8%) | 131 / 174 (75.3%) |

Per class, v1.1 grader (Syfert / CourtListener): bluebook 40/65 / 37/65; caption 16/17 / 16/17; coverage 12/12 / 7/12; history 18/18 / 17/18; misprint 7/7 / 7/7; pagination 9/9 / 9/9; quotation 6/6 / 6/6; series 1/10 / 0/10; statute 5/5 / 5/5; treatment 10/11 / 9/11; vendor 7/14 / 8/14.

The raw CourtListener arm's 24 "passes" are artifacts of the last-line fallback on tool output that was never an answer (the right string sits in the JSON body and the wrong form is above the last line); the arm is a baseline, not a comparison. The v1.0 numbers were reproduced exactly by running the v1.0 grader on the saved transcripts before the v1.1 grading.

### Layout

- `build_controls.py` and `items/controls.jsonl` are new.
- `items/evidence.jsonl` is new: the per-item v1.1 decisions (keep or drop, evidence, gold patch, new passage text). `build_tasks.py` applies it last and refuses to write an item without evidence.
- `items/bluebook.jsonl` and `items/from_fixes.jsonl` are frozen lookups sampled on 2026-10-21; they are not rebuilt for v1.1. Their builders still describe where the rows came from.
- `results/courtlistener-arm.txt` is regenerated by `score_saved.py` against the v1.1 set.

## v1.0 — 2026-10-22

187 passages, commit a5d7c79. Raw CourtListener arm 0/187 by construction (every passage the arm passed was dropped during selection).
