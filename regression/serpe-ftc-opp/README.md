# check_brief regression: Serpe v. FTC, ECF 90

A filed brief run through `check_brief(forum="flsd")` on 2026-11-05, with every
finding triaged by hand. The brief is the FTC's opposition and cross-motion for
summary judgment in *Serpe v. FTC*, No. 0:24-cv-61939 (S.D. Fla.), ECF 90,
filed 2026-03-23, 38 pages, ~200 citations. `brief.txt` is the `pdftotext`
dump; `items.jsonl` is one row per tool defect the run exposed.

The point is the tool, not the brief. A row is a place where `check_brief`
missed a real error, flagged a correct cite, told a downstream agent to apply
a wrong replacement, or had the data for a fix and did not offer it.

## Row shape

```
id        sp-NN
group     miss | false_positive | weak_suggestion | output
class     the defect, as a slug
text      the passage from brief.txt, verbatim (ligatures and line-wrap hyphens removed)
expected  what the tool should report on that passage
observed  what it reported on 2026-11-05 (date-stamped so a rerun can be compared)
fix       the change that closes it
```

`expected.absent` lists strings that must not appear in the output for the
row, in the same sense as the `controls.jsonl` gold in
`not-unfair-legal-benchmark`.

## How to rerun

Upload `brief.txt` with `brief_upload` (the inline path trims the document to
the 512 KB cap and the trimming itself produced unattached-quote artifacts on
the first run; use the upload path), then `check_brief(brief_id)` and
`get_brief_results` page by page. For each row, find the cite or quote in the
body and compare against `expected`.

## Priority

The rows that give a downstream agent wrong instructions, or miss outright:

| rows | defect |
|---|---|
| sp-11 | `unchecked` quotes land in `corrections[]` with an unrelated `replace_with`; `corrections_note` says apply it verbatim |
| sp-12, sp-13, sp-14 | bracketed alterations scored as misquotes; `check_brief` and `verify_quote` disagree on the same quote |
| sp-15 | `Id.` after an agency order binds to the last case |
| sp-01 | a cite with no reporter token is dropped silently |
| sp-02 | a short form with a party name gets no name check |

Then the year-check and cluster-mapping false positives (sp-17 to sp-20), the
style lint that would have caught five real typos (sp-04 to sp-07), and the
suggestion rows (sp-22 to sp-24).

## What the run got right

Kept here so a fix does not regress them:

- *Darby v. Cisneros* quote routed to `attribution_doubt` (the quoted words
  are statutory text).
- `name_mismatch` on 808 F. Supp. 3d 1 (the brief's *VHS* cite points at a
  different case).
- `pin_before_first` on *Brunell*, 48 How. Pr. 435, 43.
- `year_mismatch` on *Del Monte Dunes*, 526 U.S. 687 (1991) — the case is 1999,
  and the brief has 1991 in both the table and the body.
- `exists_unindexed` via the citing corpus for *Oklahoma I*, 145 S. Ct. 2836,
  and *YAPP*.
