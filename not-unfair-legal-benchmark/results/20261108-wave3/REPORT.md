# Wave 3, 2026-11-08 (v1.3 CANDIDATE, not in the set)

Status: staged for Graham's review. `items/tasks.jsonl`, `VERSION` and `CHANGELOG.md` are untouched. Nothing is
committed or pushed.

## What it is

42 candidate passages in `items/wave3_candidates.jsonl`, built by `build_wave3.py` (no network unless `--network`):

| | shape (i) | shape (ii) | total |
|---|---:|---:|---:|
| `date` (new class), ids `dt-<court>-<n>` | 10 right year, CL stores another | 10 CL's stored year, CL confirms it | 20 |
| `regional` class A, ids `rg3-<rep>-a<n>` | 7 printed number, CL: NOT FOUND | 5 CL's number, CL: FOUND | 12 |
| `regional` class C, ids `rg3-<rep>-c<n>` | 2 | 2 (CL: AMBIGUOUS) | 4 |
| controls `dt-co-1..6` (correct cite, correct year) | | | 6 |

Every network reply is on disk here: `syfert/` (live Syfert MCP check_citation + search_cases bodies), `cl/` (raw
CourtListener `analyze_citations` bodies, `<id>.txt`, with the exact passage sent in `<id>.in`; `cl/stale/` keeps
10 replies to passages that were re-shaped before the final build), `cl/health.json`.
Other files: `pool_*.jsonl`, `evidence_*.jsonl`, `pre_cl.jsonl`, `drops.jsonl`, `spares.jsonl`,
`cl_verdicts.jsonl`, `summary.json`.

## Date class: how it was drawn

Source: DATE176 `date_fix.tsv` (286 corrections), with DATE151 `date_ev2.jsonl` (citer votes, example snippets,
volume band) and `date_hold.json` (name, cite). 247 of the 286 are Maryland (A.2d, 1950s volumes); the class is
capped at 10 Maryland + 10 other courts.

1. Pool (`pool_date.jsonl`, 53 rows): every non-Maryland row except the five M.S.P.R. rows (CL also gives those a
   circuit or Supreme Court court id, two errors at once) and an "Opinion of the Justices" caption; Maryland rows
   spread over CL's stored-year decades (1960s-2000s), strongest by votes, one per volume. Cite used: the national
   reporter cite where the row has one (Ex parte Webb has only `153 Tex. 234`).
2. Evidence, per row, on the live Syfert MCP (now serving the corrected years):
   - `check_citation(cite, expected_case_name)` must resolve to the cluster with a bluebook carrying the corrected
     year.
   - `search_cases` `<party> w/15 "<cite>"` (both spellings, and the parallel cite; party surname as a fallback)
     must return 2+ citing opinions whose snippet names the case within 160 characters before the cite and whose
     first year parenthetical after the cite is the corrected year.
   - No snippet may print CL's stored year, and at most a third of them may print some other year.
   - The corrected year must sit inside the p10-p90 year span of the volume (CL-derived meta, read-only), and the
     stored year must be more than 5 years outside it.
   - No other cluster may sit at the cite.
   - Neither year string may occur in the cite or the name.
3. Shapes alternate. Passage = the Syfert bluebook name + cite + `(<court> <year>)`, where the year is the corrected
   one (i) or the stored one (ii). Gold, both shapes:
   - `right` = the cite;
   - `any_of` = the corrected year with `verdict_line: true` (on the ANSWER line, not negated);
   - `wrong` = the stored year (not on the ANSWER line);
   - `absent` = rejection / misprint phrases.

   No gold string has a month or a day. Evidence per item: stored CL date, corrected year, DATE151 votes and
   example, the volume band, the volume check, 2-4 quoted citing snippets (cluster id, name, date, printed year), and
   how many citing opinions are dated *before* the stored year (0-11; e.g. 11 opinions cite "2008" Travelers v.
   Thompson before 2008).

Echo hole: no shape (ii) passage contains its gold year (the builder checks). Shape (i) passages contain the gold
year by design, as controls do (see decision 1).

## Regional: how it was drawn

Same code as `build_regional.py` (imported; `gather`, `evaluate`, `build_item` unchanged), new ledgers:
RESCORE166 `fixA2b.json` (102) and `fixC2.json` (42). Rows already in `tasks.jsonl`, `regional.jsonl` or the
v1.2 ledgers (one: cid 3306560) were excluded. Pool: class A, 3 per reporter in 12 reporters; class C, 3 each in
N.E.2d, S.E.2d, N.W. and P., with single-other-case rows first. Quota: 1 per stratum, 2 for P. and So. (the most
class A rows). Shapes alternate by stratum. Ids `rg3-*` do not collide with v1.2's `rg-*`.

## Controls

There are 6 controls: 3 Maryland A.2d cases from the same 1950s volumes as the Maryland traps, plus 89 A.2d (Pa.),
163 N.W.2d (Minn.) and 232 U.S. They were checked like this:
- none is in any fix ledger, `neigh.jsonl`, or the 4,962-row DATE151 date-suspect list;
- each has a green flag, a name match, and a year inside its volume span;
- 2-3 citing snippets print the same year and none prints another.

Each passage is the cite with its year. Gold: the cite, plus the year on the ANSWER line, and no misprint, rejection
or wrong-year phrases.

## Drops

- **Evidence: 23** (`drops.jsonl`).
  - Date (9): another cluster at the cite (Sexton v. Dreyfus 219 U.S. 339, Perrin 232 U.S. 478, The Eliza Lines
    199 U.S. 119, Scott v. State 33 Tenn. 629); fewer than two snippets printing the year (Friend v. Talcott,
    Gattegno, City of Casselton, Holland v. State, Evergreen Amusement).
  - Regional (10): 9 thin, 1 mixed (182 N.E.2d 552).
  - Controls (4).
- **CourtListener: 1 of 59 trap candidates.** `dt-pa-1` Wallace v. Wallace, 89 A.2d 769 (Pa. 1952). CL stores
  1852-04-18, but its parallel-citation line carries `1952 Pa. LEXIS 433`, so the raw body has the right year and no
  1852 on its last line, and the grader passes it. In every other date body CL showed the stored year, with no LEXIS
  year beside it. Regional: shape (i) NOT FOUND every time; shape (ii) FOUND on the old number (A) or AMBIGUOUS
  (C), never printing the corrected number. Calls: 69 (59 + 10 after re-shaping), 1 every 2 s, no auth trouble.
- **Review: 1.** `rg3-nw2-a1` Sweeney v. Union State Bank. The citers print 22 N.W.2d 657 as *In re Sweeney's
  Estate*, but CL's 24 N.W.2d 406 is another volume and page. It may be a separate opinion (on rehearing), not a
  misnumbered one. It is excluded after the CL step, so ids don't shift. N.W.2d has no spare.
- Spares, 17: good rows not needed (`spares.jsonl`).

## Grader checks

- `python3 test_grade.py`: 24 passed.
- 267 hand-built answers through `grade.grade_item(answer, gold, passage)`, 0 surprises:
  - Date items: a good answer passes, and so does "correct as written" (i).
  - Date items fail on: the stored year on the ANSWER line; both years on it; the year only in the explanation; a
    negated year; a rejection; a tool echo followed by "no answer from the tool".
  - A bare echo of the passage passes shape (i) and fails shape (ii).
  - Regional items and controls behave as in v1.2.
- `grade.self_check` passes on all 42.

## For Graham to decide

1. **Shape (i) date passes an echo.** The passage *is* the right answer, so an extractor that repeats it passes,
   as with controls. A stricter version would also require the official parallel cite (e.g. `203 Md. 574`), which is
   a different skill. I left it as is.
2. **The date gold sits on the ANSWER line** (`any_of` + `verdict_line`, the treatment mechanism), because "1954"
   anywhere in an explanation is too weak. Alternatively, `right: ["(Md. 1954)"]` anywhere, but that is brittle on
   court forms.
3. **Golds I'm least sure of:**
   - `dt-md-9` District Heights (votes 1953: 27, 1952: 3; one quoted snippet prints 1952);
   - `dt-minn-1` and `dt-mich-1` (one-off 1969 / 1965-75 votes);
   - `dt-ri-1` (one 1962 vote).

   All are majority-clear.
4. **Class mix:**
   - 10 of 20 date traps are Maryland 1950-56 A.2d, because that is where the fixes are.
   - `dt-nysd-1` Escott v. BarChris is tagged `bare_model_answerable`.
   - `dt-tex-1` uses the official Tex. cite only; Bluebook would want 266 S.W.2d 855.
5. **Count:** 36 traps + 6 controls (target about 20 + 16 + 6). Regional is 16 with no N.W.2d, and none in N.E.2d
   class A, which had 1 pool row and it was mixed.
6. Raw CL bodies carry a "possible hallucinated citation" warning on the Bluebook-abbreviated names
   (`Travelers Ins. Co.`, `Emp. Sec. Bd.`), controls included. This is not graded, but a model reading CL may be
   pushed toward a false rejection.

## Items

| id | shape | passage | gold | CL raw | citers quoted |
|---|---|---|---|---|---|
| dt-minn-1 | i | Travelers Ins. Co. v. Thompson, 163 N.W.2d 289 (Minn. 1968). | 1968 on ANSWER line, not 2008 | status=FOUND cluster=2011235 cl_year=2008 | 4 |
| dt-mich-1 | ii | Bias v. Ausbury, 120 N.W.2d 233 (Mich. 2005). | 1963 on ANSWER line, not 2005 | status=FOUND cluster=1890677 cl_year=2005 | 4 |
| dt-tex-1 | ii | Ex parte Webb, 153 Tex. 234 (1964). | 1954 on ANSWER line, not 1964 | status=FOUND cluster=5082371 cl_year=1964 | 4 |
| dt-ri-1 | i | Capitol Bldg. Co. v. Langton, 221 A.2d 99 (R.I. 1966). | 1966 on ANSWER line, not 1981 | status=FOUND cluster=1993035 cl_year=1981 | 4 |
| dt-nysd-1 | ii | Escott v. BarChris Constr. Corp., 283 F. Supp. 643 (S.D.N.Y. 1976). | 1968 on ANSWER line, not 1976 | status=FOUND cluster=1906035 cl_year=1976 | 4 |
| dt-pa-2 | i | Verecchia v. De Siato, 45 A.2d 8 (Pa. 1946). | 1946 on ANSWER line, not 1933 | status=FOUND cluster=4090997 cl_year=1933 | 4 |
| dt-illappct-1 | ii | Thompson v. Fid. & Cas. Co., 148 N.E.2d 9 (Ill. App. Ct. 1971). | 1958 on ANSWER line, not 1971 | status=FOUND cluster=2240981 cl_year=1971 | 4 |
| dt-ca5-1 | i | Southland Ice Co. v. City of Temple, 100 F.2d 825 (5th Cir. 1939). | 1939 on ANSWER line, not 1989 | status=FOUND cluster=6977953 cl_year=1989 | 4 |
| dt-minn-2 | ii | Minnesota Canal & Power Co. v. Fall Lake Boom Co., 148 N.W. 561 (Minn. 1894). | 1914 on ANSWER line, not 1894 | status=FOUND cluster=8021727 cl_year=1894 | 3 |
| dt-ark-1 | i | Bailey v. Com. Union Bank, 269 S.W.2d 314 (Ark. 1954). | 1954 on ANSWER line, not 1964 | status=FOUND cluster=1531533 cl_year=1964 | 3 |
| dt-md-1 | i | Bd. of Med. Examiners v. Steward, 102 A.2d 248 (Md. 1954). | 1954 on ANSWER line, not 1964 | status=FOUND cluster=1472326 cl_year=1964 | 4 |
| dt-md-2 | ii | Mahnke v. Moore, 77 A.2d 923 (Md. 1972). | 1951 on ANSWER line, not 1972 | status=FOUND cluster=2352629 cl_year=1972 | 4 |
| dt-md-3 | i | Williams v. State, 102 A.2d 714 (Md. 1954). | 1954 on ANSWER line, not 1982 | status=FOUND cluster=1471848 cl_year=1982 | 4 |
| dt-md-4 | ii | Bryant v. State, 115 A.2d 502 (Md. 1991). | 1955 on ANSWER line, not 1991 | status=FOUND cluster=2333104 cl_year=1991 | 4 |
| dt-md-5 | i | Appel v. Hupfield, 84 A.2d 94 (Md. 1951). | 1951 on ANSWER line, not 2001 | status=FOUND cluster=2071746 cl_year=2001 | 4 |
| dt-md-6 | ii | Globe Indem. Co. v. Victill Corp., 119 A.2d 423 (Md. 1969). | 1956 on ANSWER line, not 1969 | status=FOUND cluster=2379026 cl_year=1969 | 4 |
| dt-md-7 | i | Baltimore Transit Co. v. State ex rel. Castranda, 71 A.2d 442 (Md. 1950). | 1950 on ANSWER line, not 1974 | status=FOUND cluster=2174641 cl_year=1974 | 3 |
| dt-md-8 | ii | Levi v. Schwartz, 95 A.2d 322 (Md. 1980). | 1953 on ANSWER line, not 1980 | status=FOUND cluster=1921828 cl_year=1980 | 4 |
| dt-md-9 | i | Dist. Heights Apts. v. Noland Co., 95 A.2d 90 (Md. 1953). | 1953 on ANSWER line, not 1998 | status=FOUND cluster=1921535 cl_year=1998 | 4 |
| dt-md-10 | ii | Watson v. State, 117 A.2d 549 (Md. 2001). | 1955 on ANSWER line, not 2001 | status=FOUND cluster=1531504 cl_year=2001 | 4 |
| rg3-se-a1 | i | Tedder v. Tedder, 94 S.E. 19. | 94 S.E. 19 + date/court | status=NOT FOUND cluster=None | 4 |
| rg3-se2-a1 | ii | Bolen v. Strange, 6 S.E.2d 46. | 6 S.E.2d 466 | status=FOUND cluster=4115584 | 4 |
| rg3-nw-a1 | i | Burt v. Winona & St. Peter Railroad, 18 N.W. 285. | 18 N.W. 285 + date/court | status=NOT FOUND cluster=None | 4 |
| rg3-ne-a1 | i | Hodge v. Sloan, 17 N.E. 335. | 17 N.E. 335 + date/court | status=NOT FOUND cluster=None | 4 |
| rg3-p-a1 | i | Campbell v. Genshlea, 180 P. 336. | 180 P. 336 + date/court | status=NOT FOUND cluster=None | 4 |
| rg3-p-a2 | ii | Pilmer v. Boise Traction Co., 91 P. 432. | 94 P. 432 | status=FOUND cluster=5337728 | 4 |
| rg3-p2-a1 | ii | Reynard v. City of Caldwell, 42 P.2d 293. | 42 P.2d 292 | status=FOUND cluster=3415671 | 4 |
| rg3-a-a1 | i | White v. Old York Road Country Club, 178 A. 3. | 178 A. 3 + date/court | status=NOT FOUND cluster=None | 4 |
| rg3-so-a1 | ii | Fitzhugh v. City of Jackson, 97 So. 90. | 97 So. 190 | status=FOUND cluster=8038243 | 4 |
| rg3-so-a2 | i | Butterfield Lumber Co. v. Guy, 46 So. 78. | 46 So. 78 + date/court | status=NOT FOUND cluster=None | 4 |
| rg3-sw-a1 | i | Leahy v. Mercantile Trust Co., 247 S.W. 396. | 247 S.W. 396 + date/court | status=NOT FOUND cluster=None | 4 |
| rg3-sw2-a1 | ii | Barnett, Admr. v. Couey, Admr., 27 S.W.2d 767. | 27 S.W.2d 757 | status=FOUND cluster=3553729 | 4 |
| rg3-ne2-c1 | i | Berg v. Schreiber, 92 N.E.2d 88. | 92 N.E.2d 88 + date/court | status=NOT FOUND cluster=None | 2 |
| rg3-se2-c1 | ii | Jackson v. Meadows, 278 S.E.2d 150. | 278 S.E.2d 8 (old no. = Tyson v. State) | status=AMBIGUOUS cluster=None | 4 |
| rg3-nw-c1 | i | Fisher v. Nicola, 241 N.W. 478. | 241 N.W. 478 + date/court | status=NOT FOUND cluster=None | 2 |
| rg3-p-c1 | ii | People v. Foster, 292 P. 142. | 192 P. 142 (old no. = In Re Forbes) | status=AMBIGUOUS cluster=None | 2 |
| dt-co-1 | control | State ex rel. Emp. Sec. Bd. v. Rucker, 126 A.2d 846 (Md. 1956). | correct as written, 1956 | status=FOUND cluster=2097021 cl_year=1956 grade=True (grader passes the raw CL body) | 3 |
| dt-co-2 | control | Palmer v. State, 137 A.2d 119 (Md. 1957). | correct as written, 1957 | status=FOUND cluster=1933376 cl_year=1957 grade=True (grader passes the raw CL body) | 2 |
| dt-co-3 | control | Hancock v. Stull, 86 A.2d 734 (Md. 1952). | correct as written, 1952 | status=FOUND cluster=1966286 cl_year=1952 grade=True (grader passes the raw CL body) | 2 |
| dt-co-4 | control | Rodney v. Staman, 89 A.2d 313 (Pa. 1952). | correct as written, 1952 | status=FOUND cluster=1443132 cl_year=1952 | 2 |
| dt-co-5 | control | Raymond v. Baehr, 163 N.W.2d 51 (Minn. 1968). | correct as written, 1968 | status=FOUND cluster=2011637 cl_year=1968 grade=True (grader passes the raw CL body) | 3 |
| dt-co-6 | control | Swift v. McPherson, 232 U.S. 51 (1914). | correct as written, 1914 | status=FOUND cluster=98057 cl_year=1914 grade=True (grader passes the raw CL body) | 3 |

## Draft CHANGELOG section (not applied)

```markdown
## v1.3 — (date of release)

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
```
