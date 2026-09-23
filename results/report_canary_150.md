# citebench report

generated 2026-09-23T15:57:31 from `results/results_canary.db` — HEADLINE SLICE: questions <= q0150 only (same questions for every run)

## Metrics per (model, arm)

| model | arm | run | answered | errors | graded | cites | fabricated_rate | pin_refs | near_miss_share | fabricated_strict_rate | court_propagated | retracted | misgrounded_rate | paraphrase_share | quote_unattributed | red_rate | gold_recall | gold_equiv | abstain_rate | warned_rate (bad-law n) | avg tool calls | avg latency s | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| local-gemma | mcp | local-gemma:mcp:v2 | 150 | 0 | 150 | 228 | 1.8% | 5 | 25.0% | 2.2% | 0 | 0 | 0.9% | 50.0% | 0 | 4.9% | 88.0% | 97.3% | 0.0% | 22.2% (18) | 2.5 | 142.7 | 0.0000 |
| local-gemma | mcp | local-gemma:mcp:v2+check | 50 | 0 | 0 | 0 | n/a | 0 | n/a | n/a | 0 | 0 | n/a | n/a | 0 | n/a | n/a | n/a | n/a | n/a (0) | 3.6 | 138.6 | 0.0000 |

Grader version(s): `g8-pinref-20260923`

## bare -> mcp delta (mcp minus bare, on questions graded in both arms)

| model | tag | common q | Δ fabricated_rate | Δ misgrounded_rate | Δ red_rate | Δ gold_recall | Δ abstain_rate | Δ warned_rate |
|---|---|---|---|---|---|---|---|---|
| (no model has both arms graded yet) | | | | | | | | |

## vs `results/results.db` (same model and arm; questions graded in both runs)

| model | arm | run | db | common q | cites | fabricated_rate | pin_refs | near_miss_share | fabricated_strict_rate | misgrounded_rate | quote_unattributed | red_rate | gold_recall | gold_equiv | abstain_rate | avg tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| local-gemma | mcp | local-gemma:mcp:v1 | `results.db` | 150 | 287 | 0.3% | 1 | 0.0% | 1.4% | 2.8% | 0 | 3.2% | 70.7% | 90.0% | 0.0% | 2.2 |
| local-gemma | mcp | local-gemma:mcp:v2 | `results_canary.db` | 150 | 228 | 1.8% | 5 | 25.0% | 2.2% | 0.9% | 0 | 4.9% | 88.0% | 97.3% | 0.0% | 2.5 |
| local-gemma | mcp | Δ (local-gemma:mcp:v2 minus local-gemma:mcp:v1) | | 150 | -59 | +1.4 pp | 4 | +25.0 pp | +0.8 pp | -1.9 pp | 0 | +1.7 pp | +17.3 pp | +7.3 pp | +0.0 pp | |

Grader version(s) in the compared DB: `g8-pinref-20260923`

Definitions: fabricated_rate = n_fabricated/n_cites (headline: unresolved cites that reconcile.py could NOT match to a real, not-yet-indexed case); fabricated_strict_rate = (n_fabricated + n_unindexed)/n_cites (every cite the reporter index cannot resolve, for transparency); pin_refs = bare pinpoints ('223 So. 2d 102' after '223 So. 2d 100') folded into the resolved authority they pin, not counted as cites (g8); near_miss_share = share of fabricated cites tagged near_miss: an interior page of an uncited case per the reporter index, or a cited / gold case's cite in the wrong reporter series (g8; still fabricated); misgrounded_rate = (n_name_mismatch + n_quote_absent)/n_cites; court_propagated = fabricated cites that are real cases miscited with a wrong volume/page that >= 2 other courts' opinions repeat (g6); retracted = cites the model withdrew in the same answer, excluded from n_cites (g6); paraphrase_share = share of absent quotes that are accurate paraphrases put in quotation marks (>= 60% of the words in order; the rest are fabricated wording), graded g5+ only; quote_unattributed = quotes not found in any cited opinion whose own citation has no cluster (fabricated / unindexed cite, docket or WL cite) or with no resolved cited opinion at all: not counted in misgrounded_rate (g7); red_rate = n_red/n_verified; gold_recall = mean(gold_hit) (headline); gold_equiv = mean(gold_equivalent): gold_hit, or a cited opinion whose text holds a >= 12-word verbatim run of the question's proposition (g7; the paired delta table stays on gold_recall); abstain_rate = mean(abstained); warned_rate = mean(warned_treatment) over questions whose gold_flag is yellow/red only (count in parentheses). Rates are pooled over answers. See grade.py docstring for how check_brief output maps to each count.
