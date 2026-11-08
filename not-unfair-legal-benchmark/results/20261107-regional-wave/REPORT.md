# Regional-reporter wave, 2026-11-07 (v1.2 CANDIDATE, not in the set)

Status: staged for Graham's review. `items/tasks.jsonl`, `VERSION` and `CHANGELOG.md` are untouched. Nothing is committed.

## What it is

48 candidate passages in `items/regional_v12_candidates.jsonl`: 41 traps built from tonight's regional reporter
number corrections (RESCORE166 class A `fix1332.json`, class C `classC.json`; FIX154 `fix91.json` was in the pool,
one row survived: `rg-p-a2` State v. Lundhigh) and 7 new controls. Builder: `build_regional.py` (no network unless
`--network`). Every network reply is on disk here: `syfert/` (check_citation + search_cases bodies), `cl/` (raw
CourtListener `analyze_citations` bodies + `health.json`).

| | shape (i) right number, CL misses it | shape (ii) old CL number, CL confirms it | total |
|---|---:|---:|---:|
| class A | 14 | 14 | 28 |
| class C | 7 | 6 | 13 |
| controls | | | 7 |

Reporters: 3 traps each in S.E., S.E.2d, N.W., N.W.2d, N.E., N.E.2d, P., P.2d, A., A.2d, So., S.W., S.W.2d
(2 A + 1 C each) and 2 in So. 2d (no class C row exists for So. 2d). Decision years 1890s-2010s
(1890s 3, 1900s 4, 1910s 5, 1920s 8, 1930s 4, 1940s 2, 1950s 4, 1960s 5, 1970s-2010s 5). Error kind:
27 same volume / wrong page, 14 same page / wrong volume.
Controls: 120 S.E. 64, 450 N.W.2d 6, 150 N.E. 9, 600 P.2d 1, 130 A. 81, 700 So. 2d 120, 250 S.W. 11 (1923-1997,
first and second series, so a control cannot be told from a trap by era; none is in any fix ledger or neigh.jsonl;
green flag; name match; three citing opinions quoted, each printing name + cite).

## How it was drawn

1. Pool (`pool.jsonl`, 120 rows): per reporter, class A top 5 and class C top 4 by n_alt, one per decade first;
   page `000` placeholders and clusters already in `tasks.jsonl` excluded.
2. Evidence (`evidence_raw.jsonl`, 74 rows reached; a stratum stopped at quota + 1 spare):
   `check_citation(alt, expected_case_name)` must resolve to the cluster on our live MCP; `search_cases`
   `<party> w/15 "<alt>"` in both spellings (`312 S.E.2d 319`, `312 SE2d 319`) must return 2+ citing opinions,
   dated on or after the decision, whose snippet prints the number with the party name within 160 characters before
   it; `<party> w/15 "<old>"` must return none (mixed evidence = drop); the decision year must sit inside the
   p10-p90 year span of the alt volume in the CL-derived meta; no other cluster may sit at alt.
3. Shapes alternate within each stratum. Shape (i) gold: `right` = alt, `any_right` = decision date (3 spellings),
   the Bluebook parenthetical (`(N.C. 1929)`), the intermediate court string where there is one, the bare docket
   number where there is one; `absent` = rejection phrases; `wrong` = old number. Shape (ii) gold: `right` = alt,
   `wrong` = old number; class C adds `old_cite_owner` and a note naming the case that owns the old number.
4. Raw CourtListener arm: 74 calls (67 candidates incl. spares + 7 controls), one per 2 s, server health in
   `cl/health.json`. Verdicts in `cl_verdicts.jsonl`. Then the first quota per stratum that CL missed was kept; the
   other 26 good rows are in `spares.jsonl`.

Every `evidence` field carries the cluster id, the bluebook, 2-4 quoted citing opinions (cluster id, name, date,
printed form, snippet), the date check and this sentence: *the corpus behind syfert.com is itself
CourtListener-derived, so the gold does not rest on our index: it rests on the citing courts' own printed text.*

## Drops

- Evidence (7, `drops.jsonl`): fewer than two citing snippets naming the case: 128 S.E.2d 520 (State Highway Dep't
  v. Thomas), 28 N.W. 173 (McLeod v. Evans), 8 N.W.2d 822 (Katzmarek), 25 N.E. 353 (Seaman v. Koehler),
  64 A.2d 832 (Lagges Estate), 115 S.W.2d 386 (McCulloch's Adm'r), 12 S.W.2d 298 (Robertsons' Guardian).
  No row was dropped for mixed evidence, a date misfit, or another case at alt.
- CourtListener (0): the raw arm passed none of the 67 trap candidates. Shape (i): NOT FOUND on every one.
  Shape (ii): FOUND on our cluster with the old number (class A), or AMBIGUOUS listing both our case and the other
  case (all 6 class C, plus `rg-so-a1`, where CL also puts Western Union Tel. Co. v. Stokes at 54 So. 181). It never
  printed the corrected number. All 7 controls: FOUND, and the grader passes the raw body (expected for controls).

## Grader checks

`python3 test_grade.py`: 21 passed. 247 hand-written answers through `grade.grade_item` behave as intended
(good answers pass; echo of the passage, a rejection of a real cite, the old number on the ANSWER line, and both
numbers on the ANSWER line fail; a control called a misprint fails), and `grade.self_check` passes on all 48.
Echo hole: no shape (ii) passage contains its gold string, and no shape (i) `any_right` string occurs in its
passage (the builder checks both). The raw kaos/Syfert renderers' echo hole does not open here.

## For Graham to decide

1. Count: 41 traps + 7 controls is a little over the 30-40 target. Trim by dropping the So. 2d pair, or a
   shape-(i) item per reporter.
2. Class name: the items use a new `class: regional` with `shape`/`fix_class` fields. Alternatively map shape (i)
   to `coverage` and shape (ii) to `misprint`/`pagination`.
3. Class C shape (ii) vs the PROMPT: CL answers AMBIGUOUS with both cases, and the PROMPT says "If two cases
   share the citation, name both". The gold here is the corrected number, so "149 S.E. 316 is Holbrook and Rizer"
   fails. I think that is the right trap (the number does not belong to Rizer), but it's a judgement call.
4. `rg-so-c1` (56 So. 913, old 915) and `rg-sw2-a1` (65 S.W.2d 592, old 598): the old number is also a pin page
   citers print inside the same case. They are shape (i), so the gold is unaffected, but they read like pagination
   errors.
5. The date check uses year spans from the local CL-derived meta (`caselaw_meta.db`, read-only), not the reporter's
   own volume tables. Most rows are same-volume page errors, where the check is trivially met.
6. The shape (i) court fact for a state high court is the parenthetical with the year (`(Ga. 1984)`); "Ga." alone is
   too weak to count. An answer that gives only the year fails.

## Items

| id | shape | class | passage | gold | CL raw | citers quoted |
|---|---|---|---|---|---|---|
| rg-se-a1 | i | A | Holmes v. City of Fayetteville, 150 S.E. 624. | 150 S.E. 624 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 39) |
| rg-se-a2 | ii | A | Mitchell v. Leech, 48 S.E. 298. | 48 S.E. 290 | status=FOUND cluster=4123322 | 3 (n_alt 35) |
| rg-se-c1 | ii | C | Columbia Nat. Bank v. Rizer, 149 S.E. 316. | 150 S.E. 316 (old no. = Atlanta Coca-Cola Bottling Co. v. Holbrook) | status=AMBIGUOUS cluster=None | 2 (n_alt 45) |
| rg-se2-a1 | ii | A | McNeal v. State, 187 S.E.2d 272. | 187 S.E.2d 271 | status=FOUND cluster=1343458 | 4 (n_alt 81) |
| rg-se2-a2 | i | A | Russo v. Manning, 312 S.E.2d 319. | 312 S.E.2d 319 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 75) |
| rg-se2-c1 | i | C | Kilgore v. State, 305 S.E.2d 82. | 305 S.E.2d 82 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 47) |
| rg-nw-a1 | i | A | Stephenson v. Golden, 276 N.W. 849. | 276 N.W. 849 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 57) |
| rg-nw-a2 | ii | A | Harris v. Harris, 215 N.W. 681. | 215 N.W. 661 | status=FOUND cluster=3436800 | 4 (n_alt 28) |
| rg-nw-c1 | ii | C | Turner v. St. John, 77 N.W. 340. | 78 N.W. 340 (old no. = Lydick v. Gill) | status=AMBIGUOUS cluster=None | 3 (n_alt 21) |
| rg-nw2-a1 | ii | A | State v. Dunne, 15 N.W.2d 299. | 15 N.W.2d 296 | status=FOUND cluster=3437081 | 4 (n_alt 43) |
| rg-nw2-a2 | i | A | Acorn Investment Co v. Michigan Basic Property Insurance Assn, 852 N.W.2d 22. | 852 N.W.2d 22 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 38) |
| rg-nw2-c1 | i | C | Schmutzler v. North Dakota Workmen's Compensation Bureau, 49 N.W.2d 649. | 49 N.W.2d 649 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 4) |
| rg-ne-a1 | i | A | Matter of Heinsheimer, 108 N.E. 636. | 108 N.E. 636 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 51) |
| rg-ne-a2 | ii | A | Zartman v. First National Bank, 82 N.E. 137. | 82 N.E. 127 | status=FOUND cluster=3631359 | 4 (n_alt 45) |
| rg-ne-c1 | ii | C | People ex rel. Livingston v. Wyatt, 79 N.E. 830. | 79 N.E. 330 (old no. = Hodgdon v. City of Haverhill) | status=AMBIGUOUS cluster=None | 4 (n_alt 21) |
| rg-ne2-a1 | ii | A | State v. Woullard, 814 N.E.2d 964. | 813 N.E.2d 964 | status=FOUND cluster=3974136 | 4 (n_alt 162) |
| rg-ne2-a2 | i | A | People v. Damen, 193 N.E.2d 25. | 193 N.E.2d 25 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 139) |
| rg-ne2-c1 | i | C | People v. Prochut, 189 N.E.2d 290. | 189 N.E.2d 290 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 12) |
| rg-p-a1 | i | A | Berger v. Lane, 213 P. 45. | 213 P. 45 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 26) |
| rg-p-a2 | ii | A | State v. Lundhigh, 161 P. 690. | 164 P. 690 | status=FOUND cluster=5338981 | 4 (n_alt 26) |
| rg-p-c1 | ii | C | People v. Keyes, 175 P. 4. | 175 P. 6 (old no. = In Re Estate of Boselly) | status=AMBIGUOUS cluster=None | 4 (n_alt 26) |
| rg-p2-a1 | ii | A | People v. Myers, 857 P.2d 301. | 858 P.2d 301 | status=FOUND cluster=1121502 | 4 (n_alt 47) |
| rg-p2-a2 | i | A | Thomson v. Continental Insurance, 427 P.2d 765. | 427 P.2d 765 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 47) |
| rg-p2-c1 | i | C | Douglas v. Douglas, 56 P.2d 362. | 56 P.2d 362 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 41) |
| rg-a-a1 | i | A | Gaydos v. Domabyl, 152 A. 549. | 152 A. 549 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 75) |
| rg-a-a2 | ii | A | Santoro v. Mack, 145 A. 272. | 145 A. 273 | status=FOUND cluster=3325602 | 4 (n_alt 44) |
| rg-a-c1 | ii | C | Harlow v. Leclair, 136 A. 123. | 136 A. 128 (old no. = Harold v. Cannell) | status=AMBIGUOUS cluster=None | 4 (n_alt 45) |
| rg-a2-a1 | ii | A | Otis Elevator Co. v. Embert, 85 A.2d 876. | 84 A.2d 876 | status=FOUND cluster=2083463 | 4 (n_alt 35) |
| rg-a2-a2 | i | A | Dal Maso v. Board of County Commissioners, 209 A.2d 62. | 209 A.2d 62 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 32) |
| rg-a2-c1 | i | C | Gnau v. Kinlein, 141 A.2d 492. | 141 A.2d 492 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 17) |
| rg-so-a1 | ii | A | Woodson v. State, 54 So. 181. | 54 So. 191 | status=AMBIGUOUS cluster=None | 4 (n_alt 55) |
| rg-so-a2 | i | A | Stowers Furniture Co. v. Brake, 48 So. 89. | 48 So. 89 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 35) |
| rg-so-c1 | i | C | Odom v. State, 56 So. 913. | 56 So. 913 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 34) |
| rg-so2-a1 | i | A | Lucedale Veneer Co. v. Keel, 79 So. 2d 233. | 79 So. 2d 233 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 11) |
| rg-so2-a2 | ii | A | Barnes v. Buckeye Molding Co., 157 So. 2d 62. | 157 So. 2d 63 | status=FOUND cluster=8041303 | 2 (n_alt 5) |
| rg-sw-a1 | ii | A | Faires v. Cockerell, 31 S.W. 639. | 31 S.W. 190 | status=FOUND cluster=4174605 | 4 (n_alt 113) |
| rg-sw-a2 | i | A | Evans v. Illinois Central Railroad, 233 S.W. 397. | 233 S.W. 397 + date/court | status=NOT FOUND cluster=None | 2 (n_alt 61) |
| rg-sw-c1 | i | C | First National Bank of Colorado v. Brown, 23 S.W. 862. | 23 S.W. 862 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 21) |
| rg-sw2-a1 | i | A | Weatherly v. American Agricultural Chemical Co., 65 S.W.2d 592. | 65 S.W.2d 592 + date/court | status=NOT FOUND cluster=None | 4 (n_alt 51) |
| rg-sw2-a2 | ii | A | State v. Harris, 23 S.W.2d 802. | 22 S.W.2d 802 | status=FOUND cluster=3551893 | 3 (n_alt 29) |
| rg-sw2-c1 | ii | C | Shelton v. Martin, 175 S.W.2d 247. | 176 S.W.2d 247 (old no. = Uvalde Construction Co. v. Hill) | status=AMBIGUOUS cluster=None | 4 (n_alt 8) |
| rg-co-se | control | - | Breedin v. Smith, 120 S.E. 64. | correct as written | status=FOUND cluster=4123244 | 3 |
| rg-co-nw2 | control | - | Cason v. Auto Owners Insurance, 450 N.W.2d 6. | correct as written | status=FOUND cluster=2055369 | 3 |
| rg-co-ne | control | - | Kaplan v. Suher, 150 N.E. 9. | correct as written | status=FOUND cluster=6563547 | 3 |
| rg-co-p2 | control | - | U. S. Fire Insurance Co. v. Colver, 600 P.2d 1. | correct as written | status=FOUND cluster=1181142 | 3 |
| rg-co-a | control | - | Dibiase v. Garnsey, 130 A. 81. | correct as written | status=FOUND cluster=3322310 | 3 |
| rg-co-so2 | control | - | Crowell v. Clay Hyder Trucking Lines, 700 So. 2d 120. | correct as written | status=FOUND cluster=1799182 | 3 |
| rg-co-sw | control | - | Cartwright v. Cartwright, 250 S.W. 11. | correct as written | status=FOUND cluster=7867886 | 3 |

## Draft CHANGELOG section (not applied)

```markdown
## v1.2 — (date of release)

250 passages (v1.1 had 202), if the regional wave is accepted as staged.

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
`results/20261107-regional-wave/drops.jsonl`). The raw CourtListener arm passed none of the 67 candidates, so none
was dropped for that; the arm's replies are in `results/20261107-regional-wave/cl/`.

### Limitations

- Most of the wave (27 of 41) is a wrong page in the right volume; 14 are the right page in the wrong volume.
- First-series reporters dominate the eras (24 of 41 decisions are before 1940), because that is where the
  corrections are.
- One record-format fix in CourtListener (re-attaching the printed numbers) would flip the whole class.
```
