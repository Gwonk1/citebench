# citebench question set

`questions.jsonl` has 300 citation questions in the `SCHEMA.md` format. Each one asks a model to cite
authority for a proposition of law. The gold answer is the case the proposition is harvested from.
The builder is `build_questions.py`. It is seeded (`--seed 20260922`) and deterministic: two runs
produce byte-identical output.

```
# usage: python3 data/build_questions.py [--seed 20260922] [--out data/questions.jsonl] [--audit N]
```

## Sources (all opened read-only, `?mode=ro`)

| what | where |
|---|---|
| propositions (`source_row` = rowid) | `/mnt/crucial/syfertize/target_propositions_slim.db` (1.5M rows; `cache/target_propositions.db` is a symlink to it) |
| case name / date / court / reporter cites | `/mnt/caselaw/pkg/caselaw_meta.db` (`cases`, `citations`, `courts`, looked up by indexed cluster_id) |
| state vs. federal, court level | `/mnt/crucial/syfertize/cache/court_state.db` |
| `gold_flag` | `/mnt/crucial/syfertize/syfertize_deploy.db` `treatment_summary.flag_color` (the live serving flag, including curation) |
| FL DCA district | `/var/www/caselaw/cache/fl_dca_districts.db` (the same lookup case.php uses) |
| `gold_citation`, `gold_case_name` | rendered by the production `/var/www/lib/bluebook.php` (`buildBluebookCite`, `bluebookCaseName`) via `php`, so the gold string matches what syfert.com shows |

No `COUNT(*)` runs. The only full scan is the ~300 MB propositions table. Everything else is an
indexed `IN (...)` lookup.

## How the set was built

1. **Candidates.** The builder takes every proposition with `citation_count >= 5` (217k rows). For
   yellow/red clusters it also takes rows down to `citation_count >= 2`, because only about 6.6k
   clusters in the whole corpus are red or yellow (2,208 red, 4,401 yellow). There are also 1.67M
   "neutral" clusters, which are excluded because the schema only allows green, yellow and red.
2. **Text filter** (`reject_reason`). A proposition must be 12-60 words, end in a period, and read as
   a self-contained statement of law. The filter rejects:
   - fragments: a leading conjunction, relative word, modal, bare verb, adverb or participle; a
     subjectless verb phrase ("provides a mechanism…"); a sentence whose only finite verb sits inside
     a relative clause; a dangling "where/if/when…" with no main clause; a bare harmless-error or
     Strickland condition ("there is no reasonable possibility…")
   - first person, case-specific words (appellant, "in this case", "here,"), and context references
     ("this section", "these factors", "such determination")
   - quoted enacted text (`shall`): the controlling authority there is the statute or constitution,
     not the case
   - embedded case citations, supra/id./fn, star paging, stripped `§` (a double space), junk bytes,
     OCR runs, OCR line numbers, unbalanced quotes, digit-heavy text, and at least 2 non-dictionary
     tokens (proper nouns or OCR)

   Each cluster keeps its best surviving proposition, ranked by citation_count, then
   distinct_citers.
3. **Case sanity.** A candidate is kept only if all of these hold:
   - the case is `Published`
   - it has a real reporter cite (not WL/LEXIS)
   - the case name is usable, with no "Appellant", "No.", docket junk, all-caps runs, or a year in
     the name later than the decision date
   - no party-name token appears in the proposition (that catches fact-bound text)
   - the rendered primary cite fits the court:
     - SCOTUS: the U.S. volume must be within 8 of the value expected for the year
     - circuits: `F.`/`F.2d`/`F.3d`/`F.4th`
     - districts: `F. Supp.`
     - Florida: `So.`
     - the other states: their regional reporter only
     - Florida DCA: the district must resolve to "Fla. Nth DCA"
     - Cal. Ct. App. filed with a post-1960 P.2d/P.3d cite is rejected (the court id is wrong)
   - volume matches year: the decision year must be within 3 years of the median year of
     same-reporter cites within 3 volumes
4. **Stratified draw.** Each stratum is sorted by citation_count, and the draw is a seeded random
   sample from the top `4n` (widened if needed), so the questions are well cited but not all
   Twombly. About 10% of each stratum is drawn on purpose from yellow/red gold cases (`gold_flag` !=
   green). These questions test whether a model or tool notices bad law. A token-Jaccard >= 0.5
   near-duplicate check runs across the whole set, so the same boilerplate cited to several
   clusters appears only once. There is one question per gold cluster.
5. **Prompts.** There are 5 templates: a direct request, a brief-drafting request, a research
   question, "opposing counsel asserts", and a memo request. Each template names the jurisdiction.
   Federal circuit and district questions name the circuit, and SCOTUS questions say "federal". Every
   template asks for case name, reporter cite, court and year, a pinpoint if possible, and for the
   model to say so rather than guess.
6. **Hand review.** Rows rejected by eye are listed in `MANUAL_REJECT` with a reason for each. They
   are skipped at draw time, like a near-duplicate, so the rest of the seeded draw does not move.

## Stratification achieved

| stratum | courts (count) | n | green | yellow | red |
|---|---|---|---|---|---|
| fl (Florida state) | fla 102, fladistctapp 48 (all resolved to 1st–5th DCA) | 150 | 136 | 3 | 11 |
| us: SCOTUS | scotus | 20 | 18 | 0 | 2 |
| us: circuits | ca2 8, ca7 7, ca10 4, ca3 3, ca8 3, ca11 2, ca1/ca6/ca9 1 | 30 | 27 | 0 | 3 |
| us: district | nyed 3, dcd 2, flmd, nysd, nywd, vaed, ksd | 10 | 9 | 0 | 1 |
| ny | ny 9 | 9 | 8 | 0 | 1 |
| ca | cal 9 | 9 | 8 | 0 | 1 |
| tx | texcrimapp 7, tex 2 | 9 | 8 | 0 | 1 |
| ga | ga 7, gactapp 2 | 9 | 8 | 1 | 0 |
| il | ill 9 | 9 | 8 | 0 | 1 |
| pa | pa 4, pasuperct 5 | 9 | 8 | 0 | 1 |
| oh | ohio 8, ohioctapp 1 | 9 | 8 | 0 | 1 |
| nj | nj 4, njsuperctappdiv 5 | 9 | 8 | 0 | 1 |
| ma | mass 9 | 9 | 8 | 0 | 1 |
| mi | mich 4, michctapp 5 | 9 | 8 | 0 | 1 |
| **total** | | **300** | **270** | **4** | **26** |

That is 150 Florida, 60 federal and 90 from 10 other states. 30 questions (10%) have a yellow or red
gold case. Florida's yellow/red pool had only 14 usable rows, so Florida has 14 rather than 15.
Gold decision years run from 1904 to 2023, with a median of 2000. Propositions are 12-60 words
(mean 27.4).

## Rejection rates

- **Automatic text filter:** 78,358 of 217,021 scanned rows passed, so 64% were rejected. The main
  reasons were fragment starts (52k), length (19k), no terminal period (16k), relative-clause
  fragments (15k) and no finite verb (12k).
- **Case and cite sanity** removed, among others: 5,118 unusable names, 3,658 cites that did not
  fit the court, 1,987 unpublished cases, 346 with a party name in the proposition, and 44 with a
  volume/year mismatch.
- **Eyeball, random 20 of the filter-only output:** 4 of 20 (20%) rejected. The reasons were a
  context-dependent sentence, an imperative fragment, a condition clause, and "pursuant to the
  statute". This drove the extra filters above.
- **Full hand review:** 410 distinct rows were read across all build iterations and 24 were
  rejected (5.9%). These are the `MANUAL_REJECT` entries, including the 4 above.
- **Eyeball, random 20 of the delivered file** (seed 20260922): 0 were garbage and 1 was
  borderline (q0260, where "the process" leans on context).

## Known limitations

- **The gold case is the case the harvester attributes the proposition to, not necessarily its
  origin.** A proposition quoted from Anderson or Celotex but harvested from a later circuit
  opinion still has the circuit case as gold. A correct, real citation to the originating case will
  miss `gold_hit` but is not a fabrication. Grade fabrication and misgrounding with check_brief, and
  treat gold_recall as a lower bound.
- **Propositions are lowercase, as harvested.** The prompt capitalizes the first letter only, so
  proper nouns ("florida", "strickland") stay lowercase in the prompt text.
- **Some residual context dependence.** Roughly 1 in 20 propositions still leans on a noun supplied
  by the surrounding opinion text ("the process", "the question is whether…").
- **Case names are CL's.** Some are long full-party captions ("Marcus Hensley v. Carolyn W.
  Colvin", "Jonathon Knight v. State of Florida"). Initials without periods get title-cased by the
  lib ("In Re Bz", "LB v. State"). Match names fuzzily.
- **Court abbreviations patched locally.** `courts.citation_string` has non-Bluebook values that
  the lib passes through ("M.D. Penn.", "E.D.N.Y", "S.D.W. Va"). The builder patches these in
  `COURT_ABBREV_FIX` and they are logged in the bake punchlist. The lib's `pickPrimaryCitation`
  choices are otherwise untouched. For example, Illinois cases prefer `N.E.` because of the
  regional-reporter filter.
- **Florida skews to the Florida Supreme Court (102 of 150).** DCA cases whose district cannot be
  resolved ("Fla. Dist. Ct. App.") are dropped, because that is not a proper Bluebook cite, and CL's
  DCA metadata is thinner.
- **Yellow/red is sparse and red-heavy (26 red, 4 yellow).** A red flag can mean "superseded by
  statute" (e.g. Carawan) as well as "overruled" (e.g. Conley v. Gibson, Saucier). Do not assume
  every red gold answer is wrong on the specific proposition asked.
- **Pinpoint pages.** Pinpoints are requested in the prompt but not graded against this file. The
  source row's `target_pin_page` is available through `source_row` if a pinpoint grader is added.
- **The draw favours well-cited propositions**, i.e. the top 4n by citation_count in each stratum.
  That measures common-authority recall, not obscure-authority recall.
