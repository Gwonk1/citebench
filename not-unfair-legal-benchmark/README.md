# not-unfair-legal-benchmark

Version 1.1 (2026-10-25). 202 passages. See `CHANGELOG.md` for every change from v1.0.

This is the not-unfair legal benchmark. It challenges an agentic system on legal ability when that system is linked to a caselaw MCP.

The set was built unfairly, on purpose. The items are places the CourtListener corpus is deficient, and the gold is the corrected cite, the corrected court form, and the corrected text. A caselaw MCP that serves that corpus meets the same items, whichever agent is connected to it. A corpus that has already been corrected on that point passes the item. Every item is answerable from public sources: the reporter page, the court's own form, or the order itself.

It is a citation test and a bluebooking test, with a control class.

## Citation

A citation item asks whether the connected caselaw returns the right case.

A real reporter cite that was never attached to the opinion comes back missing. A one-digit misprint is a miss when the neighbor is not named. An interior page is a miss when it does not resolve to the reported first page. A wrong caption on a real cite is a miss when the caption is accepted. A caption that still carries a looseleaf service name, a caption stored as a list literal, and a caption with the front of the name cut off are that kind of miss. The same cite sent twice, once under the right name and once under a wrong name, is a miss when the wrong name disappears and nothing says it does not match.

A denial of certiorari, an orders page, or a dismissal for want of a substantial federal question is a miss when the result presents that page as the lower court's own citation. Several of those pages are attached to the lower-court opinion and to the order at the same time. One Supreme Court page from 1981 is also attached to a 1996 court of appeals case.

A Westlaw or LEXIS cite is a miss when an official or regional reporter number exists for that case. Listing the vendor cite on the answer line counts. A Florida district court of appeal opinion stored as `Fla. L. Weekly Fed. D` is a miss. That is the federal weekly. The decision's reporter is the Southern Reporter, and the court is the numbered district.

A case that has been overruled, receded from, or abrogated is a miss when the result presents it as ordinary authority. An unpublished opinion presented as published is the same kind of miss, and an opinion the court later ordered published is a miss when the answer stops at "unpublished": the current citation is the published one. A quotation is a miss when the opinion text still contains the garble that makes the quote fail.

A coverage item (a real cite the index lacks) is not passed by repeating the passage. The answer has to add one fact that is not in it: the docket number, the decision date, or the court.

Statutes and court rules are only partly in the set. Some are extracted and left unverified. A section that does not exist can be extracted and left standing. Some rule forms are not extracted at all.

## Bluebooking

A bluebooking item asks whether the court in the citation is the form a brief uses.

Florida district courts of appeal are `Fla. 1st DCA`, `Fla. 2d DCA`, `Fla. 3d DCA`, `Fla. 4th DCA`, `Fla. 5th DCA`, and `Fla. 6th DCA`. That is the form Fla. R. App. P. 9.800 prescribes and the form Florida briefs use; the instruction says so in as many words. `Fla. Dist. Ct. App.` is a miss. `3rd` is a miss where the form is `3d`.

The other courts in the set are held to the Bluebook. A spelled-out state, a missing period or space, a bankruptcy appellate panel written as `Nth Cir. BAP`, a California court of appeal with a district written into the court name, and an empty court cite are misses. `SCOTUS` is a miss for the Supreme Court. The Tax Court is `T.C.` The Court of International Trade is `Ct. Int'l Trade`. A Court of Criminal Appeals case filed as a court of appeals is a miss. For the New York Appellate Division, the Illinois Appellate Court, the Ohio Court of Appeals and the Texas Courts of Appeals, the plain Bluebook form and the department or district form are both accepted (rule 10.4(b)). The gold is the corrected court string.

## Controls

Twenty-four items (`kind: control`, ids `co-*`) are ordinary, correct citations. The right answer is the citation, correct as written. A checker that calls every cite a misprint, an interior page or a fabrication fails them. They are scored on their own row so an arm's false-positive rate can be read next to its trap score. Half are casebook cases a bare model knows; half are ordinary reported cases nobody memorises, so the two cannot be told apart by fame.

## The same task for every system

Every item is a passage. Every system gets the same instruction and is graded on the words it sends back. A bare model, a model calling an MCP, and a tool called by itself are the same kind of arm.

The instruction is `PROMPT` in `grade.py`. The passage is `text` in `items/tasks.jsonl`. The gold is strings. The instruction asks for a final line that begins `ANSWER:` and holds only the corrected citation, court form, case name or verdict. A pass means the corrected cite or the corrected court form is in the answer and the ANSWER line does not carry the bad form, a vendor cite, or a rejection of a real cite. A treatment verdict has to be on the ANSWER line and may not be negated. An answer with no ANSWER line is graded on its last non-empty line and flagged `no_answer_line`.

`grade.grade_item(answer, gold)` returns the pass or miss with the reason and the flag; `grade.grade(answer, gold)` returns `(passed, reason)`. `grade.render(task)` is the full text to send. `python3 grade_answers.py answers.jsonl` grades a file of `{"id", "answer"}` rows and prints the class table. `python3 test_grade.py` runs the grader's unit tests. `python3 score_saved.py` grades the CourtListener replies already on disk.

## Scores

Scores quoted anywhere for this benchmark before 2026-10-25 are v1.0 scores under the v1.0 grader on the 187-item set. v1.1 scores from fresh runs are pending. The v1.0 transcripts re-graded under the v1.1 grader are in `CHANGELOG.md`, labelled as re-grades.

The raw CourtListener arm (the `analyze_citations` tool called by itself, server 9386476) scored 0 of 187 in v1.0 by construction: every passage that arm passed was dropped during selection, so the baseline is zero and says nothing about the tool beyond the planted failure classes. Report model-plus-MCP arms as the comparison. The saved replies are still on disk and `score_saved.py` grades them; under the v1.1 grader their last-line fallback produces a handful of artifact passes, which are not a score.

**Raw Syfert MCP tool arm (no model), 2026-10-26, grader v1.1, 202 items, server `syfert-legal-research` 1.7.0.** `run_syfert.py` routes each item to one tool by its shape (court prompts to `find_court`; citation-shaped Bluebook items to `check_brief`; treatment items to `get_treatment`; everything else to `check_brief`, with `check_citation` as the fallback) and `render_syfert.py` writes the ANSWER line from the tool's fields alone, so the score is the tool's, not a model's. Three runs the same day, each after a server fix the earlier run pointed at:

| run | server state | traps (178) | controls (24) | total (202) |
|---|---|---|---|---|
| `results/20261026-syfert-raw` | morning build | 93 | 24 | 117 |
| `results/20261026-syfert-raw2` | + Bluebook court string on `find_court` | 133 | 24 | 157 |
| `results/20261026-syfert-raw3` | + Supreme Court orders-page cites, caption hygiene | 167 | 24 | 191 |

False positives on the controls: 0 in every run. The 11 remaining misses are listed in `results/20261026-syfert-raw3/score.txt` (two court strings, three misprint items, four pagination items, one coverage, one treatment). This arm is the server's own developers measuring their own tool against a benchmark they wrote; treat it as a floor for model-plus-Syfert arms, not as a comparison with other systems.

## Evidence

Every item carries an `evidence` field: for a case, the cluster id of the decision the gold rests on in the public corpus behind syfert.com, checked on 2026-10-25 with the live tools (check_citation, check_brief, find_case, get_treatment), with the overruling case for treatment items and the published cite for ordered-published opinions; for a court form, the Bluebook rule or Fla. R. App. P. 9.800; for a history page, the cases CourtListener attaches to the page, read from the saved reply. `items/evidence.jsonl` holds the v1.1 decision for each item that was reviewed (keep or drop, the evidence, the gold change and why).

## Limitations

- The samples are clustered. The Federal Appendix treatment items are all Tenth Circuit 2001-2004; the list-literal captions are all D.D.C. F. Supp. 3d from March 2014; the looseleaf captions are all Medicare & Medicaid Guide 1984-85; the Florida DCA items are mostly 688 So. 2d (1997). One record-format fix in the source corpus flips a whole class. Read the class rows, not only the total.
- The items tagged `bare_model_answerable: true` (interior pages of famous Supreme Court cases, garbled PDF headers, Chevron and three other famous overrulings, twelve casebook controls) can be answered without any corpus. They are sanity rows, not CourtListener traps.
- The treatment class is small (15 items) after six false "overruled" golds were dropped in v1.1.
- The gold's provenance is the corpus behind syfert.com, which is itself CourtListener- and CAP-derived with corrections layered on. Three coverage items were dropped in v1.1 because their only provenance was an aggregator's volume listing of a table page; the four that stayed resolve by name and date to one case each. An error that survives in that corpus survives here.

## Layout

The code is this directory, `citebench/not-unfair-legal-benchmark/`.

- `VERSION` is `1.1`.
- `items/tasks.jsonl` is the set. 202 passages, each with `id`, `class`, `text`, `gold`, `evidence`, `version`, and where it applies `kind: control` and `bare_model_answerable`.
- `grade.py` is the instruction and the matcher. `test_grade.py` tests it. `grade_answers.py` scores a file of answers.
- `items/pilot.jsonl`, `from_fixes.jsonl`, `bluebook.jsonl`, `courts.jsonl`, `harder.jsonl`, `controls.jsonl` are the lookups the passages were built from; `items/evidence.jsonl` is the v1.1 review of them. `build_tasks.py` rebuilds `tasks.jsonl` from all of them. `build_courts.py`, `build_harder.py` and `build_controls.py` rewrite their lookups without a database; `build_bluebook.py` and `build_from_fixes.py` describe how the 2026-10-21 samples were drawn from local fix ledgers and are kept for the record.
- `run.py` is the CourtListener arm. It sends one lookup per call and writes `results/<date>/<id>.txt`. It skips ids already on disk. Pace is one call, then 1.5 seconds.
- `clmcp.py` is the CourtListener runner. It reads `~/projects/.secrets/courtlistener.key` and sends `Authorization: Token`. The token is never printed. Read tools only. Do not call the alert or subscription tools.
- `score.py` reads a saved body into status, warning, cluster id, and statute lines. `score_saved.py` grades the saved bodies and writes `results/courtlistener-arm.txt`.
- `CHANGELOG.md` lists every gold change by item id, the grader changes, and the re-grade table.

```bash
python3 build_courts.py && python3 build_harder.py && python3 build_controls.py && python3 build_tasks.py
python3 test_grade.py
python3 grade_answers.py my-arm.jsonl --misses
python3 run.py items/pilot.jsonl --ids p10-rule
python3 report_wave.py results/20261021-courts items/courts.jsonl
```

These rows are not in `tasks.jsonl`. The 1993 and 1994 Sixth DCA items are not that court. Five vendor rows are the same page, `136 S. Ct. 871`. `p07` is a candidate reporter number. One misprint overlay names the wrong page. A trailing space and two Florida circuit strings that are only `2nd` and `3rd` are not legal answers. Passages the CourtListener arm already answered are not in the set. The thirteen rows dropped in v1.1 are listed in `CHANGELOG.md` with the reason.
