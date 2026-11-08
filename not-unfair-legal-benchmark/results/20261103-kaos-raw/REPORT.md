# kaos-citations raw arm vs the raw Syfert MCP arm — not-unfair-legal-benchmark v1.1, 2026-11-03

Arm: `run_kaos.py` — 273 Ventures' `kaos-citations` 0.1.7 (Apache-2.0, PyPI; Python 3.13 venv, `kaos-nlp-core` 0.1.15)
`extract_citations()` called by itself on every passage, offline, no model. ANSWER line = the normalized citation of
every record, else "no answer from the tool" (same convention as `render_syfert.render`). Grader v1.1, 202 items.
Run time 2.6 s for 202 passages (13 ms each, in-process). The Syfert arm's numbers are `results/20261027-syfert-raw4`.

| arm | traps (178) | controls (24) | total | traps without the echo hole | total without the echo hole |
|---|---|---|---|---|---|
| raw CourtListener `analyze_citations` (v1.0, by construction) | 0 | 0 | 0 | 0 | 0 |
| raw kaos-citations 0.1.7 | 15 | 24 | 39 | 5 | 27 |
| raw Syfert MCP 1.7.0 (raw4) | 178 | 24 | 202 | 175 | 199 |

**Echo hole (grader v1.1).** Both renderers echo the tool call, which repeats the passage text, as the first line of
the answer. `grade_item` looks for `right` and `any_of` strings anywhere in the answer, so an echoed passage that
already contains the gold string ("E.D.N.Y." in a court prompt, "1.140" in a rule passage, "garbled" in the
quotation instruction) passes with no answer at all. Regrading with the lines that begin "[" removed:
kaos 39 → 27 (ct-nyed, ct-oknb, p10-rule, st-frcrim, the six quotation items, and two controls); Syfert 202 → 199
(c10-01, c10-05, c10-06: the tool said "(unresolved: verdict not_indexed)" / "no answer", not "garbled").
Proposed v1.2 rule: strip the passage text from the answer before the `right` / `any_of` search, and treat the
"no answer from the tool" sentinel as a miss. Not applied here; a grader change is a benchmark version.

**What kaos-citations passed honestly (5 traps).** vend-01/02/03 (the passage already carries the reporter cite and
the gold is that cite) and st-frcp / st-fre (repeating "Fed. R. Civ. P. 56" / "Fed. R. Evid. 702" is the answer).
Everything that needs a corpus is a miss by construction: misprints, interior pages, wrong series, vendor cites with
a reporter equivalent, captions, treatment, history, coverage, court names (no court tool).

**Extraction quality on the 140 cite-bearing passages** (volume / reporter / page agreement between the two parsers;
the 15 treatment items are excluded because the Syfert arm called `get_treatment`, which returns no parse; the 3
quotation passages match the cite regex only on OCR garbage and neither parser extracts anything):

| | passages | kaos extracted | Syfert extracted | agree on vol/reporter/page |
|---|---|---|---|---|
| all classes except treatment / quotation | 122 | 121 | 122 | 120 |

The two kaos misses are both controls: `248 N.Y. 339` (Palsgraf: the `N.Y.` reporter is not recognised at all, with
or without a case name or year) and `192 B.R. 863` parsed as `192 Balt. C. Rep. 863` (Baltimore City Reports, court
`lawb`) instead of the Bankruptcy Reporter. The second one is the dangerous kind: a confident wrong reporter.
kaos also does not extract state statutes or state rules (`Fla. Stat. § 768.28`, `Fla. R. Civ. P. 1.140`,
`Fla. R. Crim. P. 3.850` → nothing), and it keeps a WL cite as the citation (`2003 WL 23353478`) where the gold is the
reporter cite. It does parse `(en banc)` / `(per curiam)` trailing parentheticals, pin cites, signals and
`Fla. L. Weekly Fed.`; Syfert's `check_citation` could not parse the trailing parenthetical until mcp130 (in flight).

**Reading.** kaos-citations is an extractor and says so in its README ("Identification + extraction only").
On the one thing both tools do, extraction, the parsers agree on 120 of 122 passages and kaos is the one with the
two errors. On the benchmark's actual task, saying what is wrong with a citation, an extractor scores like the raw
CourtListener arm: controls and nothing else.
