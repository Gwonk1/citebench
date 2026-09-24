# citebench report

generated 2026-09-23T20:57:50 from `/home/graham/projects/citebench/results/results.db`

## Metrics per (model, arm)

| model | arm | run | answered | errors | graded | cites | fabricated_rate | pin_refs | near_miss_share | fabricated_strict_rate | court_propagated | retracted | misgrounded_rate | paraphrase_share | quote_unattributed | red_rate | gold_recall | gold_equiv | abstain_rate | warned_rate (bad-law n) | avg tool calls | avg latency s | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-fable-5-1 | bare | claude-fable-5-1:bare:v1 | 150 | 0 | 150 | 746 | 0.3% | 0 | 0.0% | 1.7% | 0 | 0 | 7.1% | 61.7% | 1 | 2.5% | 73.3% | 85.3% | 0.7% | 55.6% (18) | 0.0 | 24.2 | 13.6124 |
| claude-fable-5-1-cc | bare | claude-fable-5-1-cc:bare:v1 | 60 | 0 | 60 | 293 | 0.0% | 1 | n/a | 1.7% | 0 | 0 | 8.2% | 45.5% | 2 | 1.7% | 73.3% | 78.3% | 1.7% | 40.0% (5) | 0.0 | 22.3 | 0.0000 |
| claude-fable-5-1-cc | mcp | claude-fable-5-1-cc:mcp:v1 | 60 | 0 | 60 | 387 | 0.3% | 0 | 0.0% | 0.8% | 1 | 1 | 1.6% | 100.0% | 0 | 1.8% | 95.0% | 95.0% | 0.0% | 80.0% (5) | 6.6 | 35.5 | 0.0000 |
| claude-opus-5-5 | bare | claude-opus-5-5:bare:v1 | 150 | 0 | 150 | 554 | 0.2% | 0 | 0.0% | 1.3% | 0 | 0 | 4.9% | 58.3% | 1 | 3.1% | 72.0% | 82.0% | 0.7% | 50.0% (18) | 0.0 | 14.6 | 4.2777 |
| claude-opus-5-5-cc | mcp | claude-opus-5-5-cc:mcp:v1 | 60 | 0 | 60 | 258 | 0.4% | 0 | 0.0% | 1.2% | 1 | 1 | 2.3% | 80.0% | 1 | 2.0% | 98.3% | 100.0% | 0.0% | 80.0% (5) | 4.7 | 21.6 | 0.0000 |
| claude-opus-5-5-cc | mcp | claude-opus-5-5-cc:mcp:v2 | 60 | 0 | 60 | 231 | 0.9% | 0 | 0.0% | 1.3% | 0 | 0 | 0.4% | 0.0% | 0 | 2.2% | 98.3% | 98.3% | 0.0% | 60.0% (5) | 4.5 | 20.0 | 0.0000 |
| claude-opus-5-5-cc | mcp | claude-opus-5-5-cc:mcp:v2+check | 60 | 0 | 60 | 242 | 0.8% | 1 | 0.0% | 1.7% | 0 | 0 | 1.2% | 50.0% | 0 | 2.1% | 100.0% | 100.0% | 0.0% | 100.0% (5) | 6.5 | 27.0 | 0.0000 |
| claude-sonnet-5-or | mcp | claude-sonnet-5-or:mcp:v1 | 60 | 5 | 55 | 264 | 0.8% | 0 | 0.0% | 1.1% | 1 | 0 | 1.1% | n/a | 0 | 1.2% | 92.7% | 94.5% | 0.0% | 80.0% (5) | 4.9 | 32.7 | 8.8240 |
| deepseek-v4-pro | bare | deepseek-v4-pro:bare:v1 | 150 | 0 | 150 | 230 | 4.8% | 0 | 27.3% | 8.7% | 0 | 0 | 38.7% | 21.7% | 3 | 2.9% | 30.0% | 44.0% | 1.3% | 11.1% (18) | 0.0 | 52.6 | 0.9268 |
| deepseek-v4.1-flash-or | bare | deepseek-v4.1-flash-or:bare:v1 | 60 | 1 | 59 | 99 | 2.0% | 0 | 50.0% | 3.0% | 0 | 0 | 16.2% | 33.3% | 0 | 1.1% | 32.2% | 49.2% | 0.0% | 40.0% (5) | 0.0 | 105.8 | 0.1629 |
| deepseek-v4.1-flash-or | mcp | deepseek-v4.1-flash-or:mcp:v1 | 60 | 2 | 58 | 277 | 0.0% | 0 | n/a | 1.4% | 0 | 0 | 2.5% | 57.1% | 0 | 1.1% | 87.9% | 87.9% | 0.0% | 80.0% (5) | 8.3 | 112.5 | 0.3707 |
| gemini-3.1-pro-or | bare | gemini-3.1-pro-or:bare:v1 | 150 | 0 | 150 | 314 | 3.2% | 0 | 20.0% | 4.5% | 0 | 0 | 18.2% | 51.8% | 11 | 4.3% | 62.7% | 74.7% | 2.7% | 22.2% (18) | 0.0 | 26.2 | 5.8154 |
| gemini-3.8-flash-or | bare | gemini-3.8-flash-or:bare:v1 | 40 | 1 | 39 | 109 | 2.8% | 0 | 0.0% | 4.6% | 0 | 0 | 28.4% | 50.0% | 0 | 2.9% | 61.5% | 76.9% | 0.0% | 50.0% (4) | 0.0 | 18.4 | 0.4251 |
| gemini-3.8-flash-or | mcp | gemini-3.8-flash-or:mcp:v1 | 40 | 37 | 3 | 4 | 0.0% | 0 | n/a | 0.0% | 0 | 0 | 0.0% | n/a | 0 | 0.0% | 100.0% | 100.0% | 0.0% | n/a (0) | 1.1 | 4.0 | 0.2120 |
| gpt-6-astra | bare | gpt-6-astra:bare:v1 | 150 | 0 | 150 | 217 | 0.0% | 0 | n/a | 0.5% | 0 | 0 | 6.0% | 46.2% | 0 | 4.6% | 58.0% | 70.0% | 0.0% | 11.1% (18) | 0.0 | 25.1 | 6.0984 |
| local-gemma | bare | local-gemma:bare:v1 | 303 | 0 | 303 | 535 | 59.3% | 2 | 36.3% | 74.2% | 0 | 0 | 28.6% | 5.3% | 103 | 2.0% | 2.6% | 3.0% | 0.0% | 0.0% (30) | 0.0 | 51.0 | 0.0000 |
| local-gemma | mcp | local-gemma:mcp:v1 | 303 | 0 | 303 | 580 | 0.7% | 4 | 50.0% | 1.7% | 0 | 0 | 4.3% | 59.1% | 0 | 3.0% | 73.9% | 89.8% | 0.0% | 16.7% (30) | 2.2 | 129.6 | 0.0000 |
| local-gemma | mcp | local-gemma:mcp:v2 | 150 | 0 | 150 | 228 | 1.8% | 5 | 25.0% | 2.2% | 0 | 0 | 0.9% | 50.0% | 0 | 4.9% | 88.0% | 97.3% | 0.0% | 22.2% (18) | 2.5 | 142.7 | 0.0000 |
| local-gemma | mcp | local-gemma:mcp:v2+check | 150 | 0 | 150 | 203 | 0.0% | 1 | n/a | 0.0% | 0 | 0 | 1.5% | 50.0% | 0 | 6.4% | 88.7% | 98.0% | 0.0% | 55.6% (18) | 3.0 | 130.6 | 0.0000 |
| local-gemma | mcp | local-gemma:mcp:v3 | 150 | 0 | 150 | 171 | 0.0% | 1 | n/a | 1.2% | 0 | 0 | 1.2% | 50.0% | 0 | 7.1% | 90.0% | 99.3% | 0.0% | 0.0% (18) | 1.4 | 85.7 | 0.0000 |
| qwen3.8-flash-or | bare | qwen3.8-flash-or:bare:v1 | 60 | 0 | 60 | 176 | 51.7% | 0 | 26.4% | 59.1% | 0 | 0 | 42.0% | 9.8% | 25 | 0.0% | 8.3% | 15.0% | 0.0% | 20.0% (5) | 0.0 | 28.4 | 0.0470 |
| qwen3.8-flash-or | mcp | qwen3.8-flash-or:mcp:v1 | 60 | 6 | 54 | 259 | 2.7% | 2 | 14.3% | 3.1% | 0 | 0 | 5.4% | 44.4% | 0 | 1.6% | 87.0% | 92.6% | 0.0% | 100.0% (4) | 7.5 | 60.2 | 0.2970 |
| qwen3.8-max | bare | qwen3.8-max:bare:v2 | 150 | 0 | 150 | 315 | 26.0% | 0 | 24.4% | 31.1% | 0 | 0 | 16.8% | 21.2% | 7 | 3.6% | 15.3% | 25.3% | 1.3% | 16.7% (18) | 0.0 | 38.2 | 1.6244 |

Grader version(s): `g8-pinref-20260923`

## bare -> mcp delta (mcp minus bare, on questions graded in both arms)

| model | tag | common q | Δ fabricated_rate | Δ misgrounded_rate | Δ red_rate | Δ gold_recall | Δ abstain_rate | Δ warned_rate |
|---|---|---|---|---|---|---|---|---|
| claude-fable-5-1-cc | v1 | 60 | +0.3 pp | -6.6 pp | +0.1 pp | +21.7 pp | -1.7 pp | +40.0 pp |
| deepseek-v4.1-flash-or | v1 | 57 | -2.1 pp | -13.4 pp | -0.0 pp | +57.9 pp | +0.0 pp | +40.0 pp |
| gemini-3.8-flash-or | v1 | 3 | +0.0 pp | -50.0 pp | +0.0 pp | +0.0 pp | +0.0 pp | n/a |
| local-gemma | v1 | 303 | -58.6 pp | -24.3 pp | +1.0 pp | +71.3 pp | +0.0 pp | +16.7 pp |
| qwen3.8-flash-or | v1 | 54 | -48.9 pp | -36.0 pp | +1.6 pp | +77.8 pp | +0.0 pp | +75.0 pp |

Definitions: fabricated_rate = n_fabricated/n_cites (headline: unresolved cites that reconcile.py could NOT match to a real, not-yet-indexed case); fabricated_strict_rate = (n_fabricated + n_unindexed)/n_cites (every cite the reporter index cannot resolve, for transparency); pin_refs = bare pinpoints ('223 So. 2d 102' after '223 So. 2d 100') folded into the resolved authority they pin, not counted as cites (g8); near_miss_share = share of fabricated cites tagged near_miss: an interior page of an uncited case per the reporter index, or a cited / gold case's cite in the wrong reporter series (g8; still fabricated); misgrounded_rate = (n_name_mismatch + n_quote_absent)/n_cites; court_propagated = fabricated cites that are real cases miscited with a wrong volume/page that >= 2 other courts' opinions repeat (g6); retracted = cites the model withdrew in the same answer, excluded from n_cites (g6); paraphrase_share = share of absent quotes that are accurate paraphrases put in quotation marks (>= 60% of the words in order; the rest are fabricated wording), graded g5+ only; quote_unattributed = quotes not found in any cited opinion whose own citation has no cluster (fabricated / unindexed cite, docket or WL cite) or with no resolved cited opinion at all: not counted in misgrounded_rate (g7); red_rate = n_red/n_verified; gold_recall = mean(gold_hit) (headline); gold_equiv = mean(gold_equivalent): gold_hit, or a cited opinion whose text holds a >= 12-word verbatim run of the question's proposition (g7; the paired delta table stays on gold_recall); abstain_rate = mean(abstained); warned_rate = mean(warned_treatment) over questions whose gold_flag is yellow/red only (count in parentheses). Rates are pooled over answers. See grade.py docstring for how check_brief output maps to each count.
