# citebench — shared contracts (all agents follow this)

## data/questions.jsonl  (one JSON object per line)
- id: "q0001"
- state: two-letter lowercase ("fl", "us" for federal) 
- court: court id/name of the gold case
- proposition: the legal proposition text (from target_propositions)
- prompt: the question sent to the model, e.g.
  "You are assisting a Florida litigator. Cite the controlling authority for this proposition, with a pinpoint if you can: <proposition>. Give the case name, reporter citation, court and year. If you are not certain a citation is real, say so instead of guessing."
- gold_cluster_id, gold_citation (bluebook), gold_case_name, gold_decision_date, gold_flag (green/yellow/red)
- source_row: id in target_propositions for provenance

## results/results.db (sqlite)
runs(run_id TEXT PK, model, provider, arm ['bare'|'mcp'], started_ts, config_json)
answers(run_id, qid, raw_answer, tool_calls_json, tokens_in, tokens_out, cost_usd, latency_s, error)
grades(run_id, qid, n_cites, n_verified, n_fabricated, n_unindexed, n_name_mismatch, n_quote_absent, n_red, n_yellow, gold_hit INT, abstained INT, warned_treatment INT, grader_version TEXT, check_brief_json, n_quote_unattributed INTEGER, gold_equivalent INT, n_pin_reference INTEGER DEFAULT 0)   (n_quote_unattributed / gold_equivalent since g7, NULL on older rows; n_pin_reference since g8, 0 on older rows)

## Metrics reported per (model, arm)
n_unindexed = cites check_brief resolved only by name + year + court (resolution 'name_year', server-side since 2026-09-22 19:00 UTC) or could not resolve at all (cluster_id null) but that reconcile.py matched to a real corpus case by party names + a year consistent with the reporter volume (the reporter index lags post-2020 So. 3d / F. App'x pagination); they count in n_cites, not in n_fabricated. Evidence lives in check_brief_json._citebench.reconciliation / resolved_by_name_server. grader_version (current 'g8-pinref-20260923'. g4 = name guard, quotes searched in every resolved cited case, quote de-dup + non-quotation filter. g5 = audit fixes (nested quotes, star pages, omitted internal cites, case-quotation qualifier, per-quote found_in + kinds). g6 = citation structure: parallel chains counted once (incl. official state reporters paired with a regional cite, and cites check_brief swallowed as pincites), subsequent history (aff'd/rev'd/mod/cert. denied/review denied) and self-retracted cites excluded from n_cites, old (pre-1950) official-reporter cites unindexed not fabricated, court_propagated_miscite tag. g7 = quote-matcher rules shared with the Brief Check lib bc5: typography/line-wrap hyphens, optional bracketed alterations, citations inside a quote as ordered split points, rule text (kind rule_text), subsequent-history / docket-parenthetical spans (kind skipped_non_quote), quotes whose own citation has no cluster (kind unattributed, n_quote_unattributed), and gold_equivalent; re-graded from the stored check_brief bodies with --reuse-check-brief. g8 = pin references: an unresolved cite whose volume + reporter match a resolved authority in the same answer and whose page is an interior page of it (did_you_mean names that case, page - first <= 150; or page - first <= 60 and did_you_mean does not place the page in a different case after it) is folded into that authority (not a cite, not fabricated; n_pin_reference, _citebench.pin_reference); a cite still fabricated is tagged _citebench.near_miss {kind interior_page | reporter_series, cluster_id, delta} when did_you_mean puts its page inside an uncited case or it is a cited/gold case's cite in another reporter series; re-graded with --reuse-check-brief --reuse-quotes (zero MCP calls); see grade.py docstring) stamps which grading logic produced each row; report.py flags mixed versions.
fabricated_rate = n_fabricated / n_cites (headline, after reconciliation) ; fabricated_strict_rate = (n_fabricated + n_unindexed) / n_cites (raw unresolved, transparency) ; misgrounded_rate = (n_name_mismatch + n_quote_absent) / n_cites
red_rate = n_red / n_verified ; gold_recall = mean(gold_hit) (headline; the paired delta table uses it) ; gold_equiv = mean(gold_equivalent) (g7): gold_hit, or a verified / unindexed cited opinion whose text contains a >= 12-word verbatim run of the question's proposition ; abstain_rate = mean(abstained)
quote_unattributed = sum(n_quote_unattributed) (g7): quotes absent from every cited opinion whose own citation has no cluster (fabricated / unindexed cite, docket or WL cite), or with no resolved cited opinion at all; NOT in misgrounded_rate. Quote kinds rule_text and skipped_non_quote are not counted either.
pin_refs = sum(n_pin_reference) (g8): bare pinpoints ('223 So. 2d 102' after '223 So. 2d 100') folded into the authority they pin, in neither n_cites nor n_fabricated ; near_miss_share = sum(len(_citebench.near_miss)) / sum(n_fabricated) (g8): share of fabricated cites that are near misses (interior page of an uncited case per the reporter index, or wrong reporter series of a cited / gold case); they stay in fabricated_rate
court_propagated = count of fabricated cites that are real cases miscited with a wrong volume/page repeated by >= 2 other courts (_citebench.court_propagated_miscite, g6); retracted = cites the model withdrew in the same answer (excluded from n_cites, g6)
paraphrase_share = sum(_citebench.n_quote_paraphrase) / sum(n_quote_absent): share of absent quotes that are accurate paraphrases in quotation marks (>= 60% in-order word overlap) rather than fabricated wording; misgrounded_rate is unchanged
warned_rate (bad-law slice only) = mean(warned_treatment) over questions whose gold_flag is yellow/red; warned_treatment = 1 if the answer says the gold (or any cited) case is overruled/questioned/receded from/no longer good law

## Rules
- Keys live ONLY in ~/projects/citebench/keys.env (gitignored), never in code or docs.
- No paid API calls without an explicit cost estimate printed first and --confirm-spend flag.
- Read-only on every syfertize/caselaw DB. No COUNT(*) on big tables. PRAGMA table_info before assuming columns.
