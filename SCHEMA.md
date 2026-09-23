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
grades(run_id, qid, n_cites, n_verified, n_fabricated, n_unindexed, n_name_mismatch, n_quote_absent, n_red, n_yellow, gold_hit INT, abstained INT, warned_treatment INT, grader_version TEXT, check_brief_json)

## Metrics reported per (model, arm)
n_unindexed = cites check_brief resolved only by name + year + court (resolution 'name_year', server-side since 2026-09-22 19:00 UTC) or could not resolve at all (cluster_id null) but that reconcile.py matched to a real corpus case by party names + a year consistent with the reporter volume (the reporter index lags post-2020 So. 3d / F. App'x pagination); they count in n_cites, not in n_fabricated. Evidence lives in check_brief_json._citebench.reconciliation / resolved_by_name_server. grader_version (current 'g6-parallel-20260922'. g4 = name guard, quotes searched in every resolved cited case, quote de-dup + non-quotation filter. g5 = audit fixes (nested quotes, star pages, omitted internal cites, case-quotation qualifier, per-quote found_in + kinds). g6 = citation structure: parallel chains counted once (incl. official state reporters paired with a regional cite, and cites check_brief swallowed as pincites), subsequent history (aff'd/rev'd/mod/cert. denied/review denied) and self-retracted cites excluded from n_cites, old (pre-1950) official-reporter cites unindexed not fabricated, court_propagated_miscite tag; see grade.py docstring) stamps which grading logic produced each row; report.py flags mixed versions.
fabricated_rate = n_fabricated / n_cites (headline, after reconciliation) ; fabricated_strict_rate = (n_fabricated + n_unindexed) / n_cites (raw unresolved, transparency) ; misgrounded_rate = (n_name_mismatch + n_quote_absent) / n_cites
red_rate = n_red / n_verified ; gold_recall = mean(gold_hit) ; abstain_rate = mean(abstained)
court_propagated = count of fabricated cites that are real cases miscited with a wrong volume/page repeated by >= 2 other courts (_citebench.court_propagated_miscite, g6); retracted = cites the model withdrew in the same answer (excluded from n_cites, g6)
paraphrase_share = sum(_citebench.n_quote_paraphrase) / sum(n_quote_absent): share of absent quotes that are accurate paraphrases in quotation marks (>= 60% in-order word overlap) rather than fabricated wording; misgrounded_rate is unchanged
warned_rate (bad-law slice only) = mean(warned_treatment) over questions whose gold_flag is yellow/red; warned_treatment = 1 if the answer says the gold (or any cited) case is overruled/questioned/receded from/no longer good law

## Rules
- Keys live ONLY in ~/projects/citebench/keys.env (gitignored), never in code or docs.
- No paid API calls without an explicit cost estimate printed first and --confirm-spend flag.
- Read-only on every syfertize/caselaw DB. No COUNT(*) on big tables. PRAGMA table_info before assuming columns.
