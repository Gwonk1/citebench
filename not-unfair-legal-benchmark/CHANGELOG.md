# Changelog

## Grader fix — 2026-11-10 (passages and gold unchanged, still v1.4)

`grade.py`: a `wrong` form on the ANSWER line is no longer punished when the line itself marks it as the wrong form
and also carries the corrected form. Example (item `dt-md-6`): "The year written with this citation (1969) is not the
decision year: Globe Indemnity Co. v. Victill Corp. was decided in 1956." was failed for containing 1969. Recognised
markers: "not X", "instead of X", "rather than X", "written/printed (as) X", "X is/was not ...", "X is/was
wrong/incorrect/a misprint/a typo". Every occurrence of the wrong form on the line must be so marked; a line that
asserts the wrong form anywhere ("(Md. 1969), decided 1956") still fails, and so does a line holding only the wrong
form. Tests added in `test_grade.py`; every item's self-check still passes.

Effect on saved answer files (old grader vs new, all files under `results/`): no change in any arm except the raw
Syfert arm on the wave-3 date items: `20261108-syfert-raw-wave3` 41 -> 42 of 42 (`dt-md-6`), and the pre-fix run
`20261108-syfert-raw-wave3-pre` 32 -> 42 (ten date items whose answer line quoted the wrong year while correcting
it). The raw Syfert arm on the full set is 323 of 343 under this grader (322 before). Scores quoted in earlier
entries were computed with the grader of their day.

## v1.4 — 2026-11-09

343 passages (v1.3 had 292). The 292 v1.3 passages and their gold are unchanged (a rebuild is identical apart from
the version field).

### Gold: added — two decisions on one first page (new class `samepage`, 29 traps)

Built by `build_wave4.py` from the 2026-11-09 same-first-page corrections (PAGE195). In each, CourtListener files the
case at a reporter page that is the first page of a different decision, so the case shares a "first page" with
another case. Citing opinions print a different page for it. Ids `pg-m-*` (move) and `pg-s-*` (stray).

- move (`fix_class: move`, 18): the case's only cite in that reporter is the other decision's page; citing opinions
  print another page (3+ times in the PAGE195 count) that no case holds. 9 shape (i) and 9 shape (ii):
  - shape (i): the passage gives the printed page. CourtListener returns NOT FOUND. Graded like a regional shape
    (i): the printed cite plus the decision date or the court, with no rejection and not the old page on the ANSWER
    line.
  - shape (ii): the passage gives CourtListener's page. CourtListener returns AMBIGUOUS and names both cases. The gold
    is the printed page; the old page may not be on the ANSWER line.
- stray (`fix_class: stray`, 11, all shape (ii)): CourtListener lists the right page on the case and also a stray one,
  the other decision's first page in the same volume. The passage gives the stray. CourtListener returns AMBIGUOUS.
  Shape (i) is no trap here, because CourtListener holds the right page as well.

14 reporters (P., P.2d, N.W., N.W.2d, S.W., S.W.2d, S.E., S.E.2d, A., A.2d, N.E., N.E.2d, So., N.Y.S.2d), decided
1888-1998, 16 of 29 before 1940. Each gold note names the other case at the old page.

### Gold: added — Appellate Division cites filed as N.Y.2d (new class `nyseries`, 16 traps)

From the 2026-11-09 New York series correction (XREP204, `RELABEL_free` rows). CourtListener files about 14,700
Appellate Division cites as `<vol> N.Y.2d <page>` with volumes 232-980. N.Y.2d (the Court of Appeals) ended at volume
100, so these cites are impossible. They are N.Y.S.2d cites, and no other case holds the N.Y.S.2d number. Ids `ny-8-*`
and `ny-9-*` (N.Y.S.2d volumes 850-933, decided 2008-2011). Two shapes, 8 each:

- shape (i): the passage gives the real cite, e.g. `866 N.Y.S.2d 275`. CourtListener returns NOT FOUND, so a correct
  cite looks fabricated. Graded like a coverage item: the cite plus the date or the court (`N.Y. App. Div.` with or
  without the department).
- shape (ii): the passage gives CourtListener's `N.Y.2d` label. CourtListener returns FOUND and confirms it, and its
  reply prints the official A.D.2d/A.D.3d cite as a parallel. Either the N.Y.S.2d cite or the official A.D. cite
  passes (`any_right`); the N.Y.2d label may not be on the ANSWER line.

### Controls: added (6)

`ny-co-1..3`: Appellate Division cases that CourtListener already files correctly under N.Y.S.2d (650 and 760
N.Y.S.2d). `pg-co-1..3`: ordinary cases in volumes the move traps come from (62 P., 189 S.W.). None of them is in
PAGE195, PRIM203, XREP204 or an earlier fix ledger. Each has a green flag, a name match, and two or more citing
opinions that print the cite with the name. The raw CourtListener arm passes all six.

### Evidence

Same standard as v1.2 (`build_regional.py`'s `gather` and `evaluate`, unchanged), checked with the syfert.com MCP
(`check_citation` and `search_cases`, 2026-11-09). Every item quotes two to four citing opinions that print the gold
cite within 160 characters after a party word of the name. No citing opinion prints the old cite with that name. The
decision year falls inside the printed volume's span, and no other cluster sits at the printed cite in the
CourtListener-derived meta (dated 2026-11-06, before these fixes). `build_wave4.py` adds four checks: CourtListener
holds the old cite on this case; the other case at a samepage old cite has a different party word; Syfert's Bluebook
string leads with the printed cite; and the name check matches.

The raw CourtListener arm (`analyze_citations`, saved in `results/20261109-wave4/cl/`) passed none of the 45 traps.
An item would also have been dropped if CourtListener did not show the error it is built on: for shape (ii), the
reply must return this case at the old cite; for shape (i), it must not resolve the printed cite to the case. No item
was dropped on either count. Evidence drops: 17 move, 30 stray, 5 NY, 11 controls (`results/20261109-wave4/drops.jsonl`).

### Classes used and not used

- PAGE195 move-page rows: used (18 of 79 pool rows; 4 dropped as mixed, i.e. some citers print the old page with the
  name; the A.D.2d, N.J. and N.Y.S.2d strata had no row with two named citing opinions).
- PAGE195 drop-stray rows: used (11).
- PRIM203 stray-first-page rows: none survived. 25 reached the evidence step. The So. 3d, A.3d, A.D.3d and P.3d rows
  are recent short decisions with no citing opinions. For one row (Ocean Petroleum, Co. v. Yanek, 416 Md. 74), citing
  courts print CourtListener's first-listed page, 5 A.3d 683, with the name 17 times, against PRIM203's 5 A.3d 688.
- PAGE195 drop-wrong-court rows: not used. Many of them are cites recovered by our own harvester (null CourtListener
  id), so the error is not CourtListener's.
- XREP204 `DROP_dup_of_nys` and `HOLD_*` rows: not used. The case already has its N.Y.S.2d cite, or the N.Y.S.2d
  number belongs to another case. Twin clusters at one key (e.g. Dominguez v. O'Flynn, 951 N.Y.S.2d 452) are skipped.

### Grader

No change. The N.Y.S.2d / A.D. alternatives use `any_right`.

### Limitations

- The nyseries class covers four years (2008-2011) and 850-933 N.Y.S.2d. Only rows with three or more named citing
  sentences in XREP204's count were drawn, and those are 2007-2014.
- 16 of 29 samepage decisions are before 1940.
- Stray shape (ii) items and move shape (ii) items test the same behaviour as the v1.2 class C regional items: an
  AMBIGUOUS page shared with another case.
- A single record-format fix in CourtListener (relabelling N.Y.2d > 100 as N.Y.S.2d) would flip the whole nyseries
  class.

### Review calls (2026-11-09)

- nyseries shape (ii) accepts the official A.D. cite as well as N.Y.S.2d, because a brief citing the case by its
  official cite is correct and CourtListener prints that cite. Only the impossible N.Y.2d label is a miss.
- Stray rows are shape (ii) only (see above).
- Only 1 of the 11 stray cases lists the stray first in CourtListener's citation order; the other 10 list it second.
  The AMBIGUOUS reply is the same either way.
- The modern PRIM203 strata (So. 3d, A.3d, P.3d, A.D.3d) gave their slots to the older stray strata. Those strata
  then took two rows each (N.W.2d three), which is every row they had that passed.

### Scores

Raw Syfert MCP arm on the 51 new items, grader v1.2 rules (`run_syfert.py items/wave4.jsonl`), server
`syfert-legal-research` 2.0.0, `results/20261109-syfert-raw-wave4`:

| samepage (29) | nyseries (16) | traps (45) | controls (6) | total (51) |
|---|---|---|---|---|
| 24 | 8 | 32 | 6 | 38 |

No false positives. The nyseries shape (i) items all pass: the N.Y.S.2d relabel had reached the index. All 8
shape (ii) items miss, because `check_brief` calls `871 N.Y.2d 170` fabricated ("volume cannot exist") or not
indexed, and proposes neither the N.Y.S.2d cite at the same volume and page nor the A.D. parallel. The 5 samepage
misses are shape (ii): the old page now resolves only to the other case. `check_brief` reports a name mismatch and
offers the other case, not the named case's printed page. As in v1.2 and v1.3, Syfert's index was corrected from
the evidence the gold rests on, so this arm checks whether the corrections reach the tool. It is not an independent
comparison.

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
