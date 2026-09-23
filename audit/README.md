# citebench grader audit: the "misgrounded" column

Review page (OIDC-gated): https://www.isyfert.com/enrich/citebench-audit/
Saved verdicts (cloud, append-only JSONL, latest line per id wins): `/var/lib/syfert/citebench-audit/verdicts.jsonl`

## What is in the packet

`packet.json` holds 60 items drawn from `results/results.db` (opened `?mode=ro`) on 2026-09-22 20:39 UTC,
seed 20260922, paid runs only (`run_id` not like `mock%` / `local%`), grader_version g3-nameyear-20260922.
Several runs (sonnet mcp, gemini, deepseek) were still being written, so the frame is a snapshot; it is
recorded in `packet.json` (`frame`, `allocation`) and the sample is frozen.

- **Q01-Q35**: quotes the grader counted in `n_quote_absent` (`_citebench.quotes_absent`).
- **Q36-Q50**: quotes the grader extracted and found (`quotes_extracted` minus `quotes_absent`).
- **N01-N10**: clusters counted in `n_name_mismatch` (`_citebench.mismatch_clusters`), claimed vs resolved name.

Each stratum is split across runs in proportion to the run's total `n_cites` (largest remainder, capped by
what the run has), then drawn with `random.Random(20260922).sample` within each run.

The grader's quote verdict is per answer, not per cite: a quote is "absent" when it is in none of the resolved cases
the answer cites. Each card shows:

- **Grader attribution.** From rows graded g5+ it comes only from `_citebench.quote_results[]`: "found in: <case>"
  (verbatim/near), or "not found in any of: <cases searched>; closest: <case> (<paraphrase_ratio>)".
  Rows graded before g5 (g3/g4) did not record which case a quote was checked against; the card says so and lists
  the opinions that grader searched (g3: verified cases; g4: every resolved cited case).
- **The answer's own attribution**, resolved from the answer text (`model_attribution` in build_packet.py), in order:
  the quote inside the explanatory parenthetical of the cite before it (`Cite (Fla. 2012) ("...")`); else a cite
  right after the quote on the same line (full cite, `Id.` / `id.` at N resolved to the preceding case citation,
  short form `Commerce, 695 So. 2d at 385` matched by volume + reporter, `Name, supra` matched by party name);
  a cite after the quote introduced by "citing" / "quoting" is not taken as the source; a new prose sentence
  ("The Court cited Mobil Oil v. Shevin, ...") is not taken either; else the closest preceding citation or case-name
  mention ("the very next sentence in Mejia (at 1177) notes: ..."). check_brief's quote pairing is NOT used
  (it paired Q35 with Anderson; nearest-full-cite put Q11 on Tipper instead of the "Id." antecedent, Commerce).
- **The answer's sentence, verbatim**, quote highlighted and the cite underlined (a separate cite sentence when the
  cite is in another paragraph), so the auditor sees the attribution the model made.
- **Closest passage from THAT case**: the found-in case, else the grader's closest case, else (pre-g5) the answer's
  case; the longest word-for-word run with 300 chars either side. A longer run in another searched case is offered
  in a collapsed line. check_brief's own quote check is still shown, labelled with the case it paired.

Two quirks visible in the sample: Q12 and Q16 are the same sentence extracted twice from one answer (with and
without the final period), because `extract_quotes` found it once by straight-quote and once by curly-quote pairing;
both count in `n_quote_absent`. Items like Q20 ("quoting Fed. R. Civ. P. 56(c)") and Q33 (a Westlaw topic name) are
quoted text that is not offered as a case quotation.

## How the result feeds the methodology

Per the page's instructions, "grader right" on an absent item means the passage is genuinely not in any
cited case; on a found item that it is there; "grader wrong" also covers non-quotations counted as absent quotes.

    ssh cloud-ts cat /var/lib/syfert/citebench-audit/verdicts.jsonl | python3 audit/score.py

**Grader precision on quote verdicts** = right / (right + wrong) over the 50 quote items (35 absent + 15 found),
with a 95% Wilson interval: centre (p + z²/2n)/(1 + z²/n), half-width z·sqrt(p(1-p)/n + z²/4n²)/(1 + z²/n), z = 1.96.
Unsure items are reported and left out of n. score.py also prints the absent and found strata separately
(the absent stratum is the one that drives misgrounded_rate) and the 10 name-mismatch items on their own.

This fills the "[Placeholder: results of a human audit of 50 ...]" in docs/METHODOLOGY.md, section 3,
"The grader has an error rate": auditor, agreement x/50, and which way the disagreements run (the grader
calling real quotes absent inflates misgrounded_rate; calling invented quotes found deflates it). Note that
the placeholder describes a sample stratified across fabricated / misgrounded / stale / clean; this packet
covers the misgrounded column only, so the text should say so, or the other columns need their own audit.
Because the strata are not sampled at their population rates (35:15 vs about 304:660 absent:found quotes),
the pooled 50-item precision is a descriptive figure; to estimate the corrected misgrounded_rate, weight each
stratum's error rate by its population count from `packet.json` `frame`.

Rebuild attribution only, keeping the frozen sample (ids, quotes, verdicts, frame), into a scratch dir first:
`PYTHONDONTWRITEBYTECODE=1 python3 audit/build_packet.py --frozen audit/packet.json --out /path/packet.json && python3 audit/build_page.py --packet /path/packet.json --out /path/index.html`.
A frozen item whose row has since been regraded keeps the verdict being audited; the card notes the new verdict,
or that the new grader no longer checks that span (with its skip reason).

Redraw (only if you mean to; the sample changes if the DB has grown):
`PYTHONDONTWRITEBYTECODE=1 python3 audit/build_packet.py && python3 audit/build_page.py`, then scp `index.html` as in DEPLOY.md.
