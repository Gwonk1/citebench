# citebench: citation-integrity benchmark (runner + grader). Contracts: SCHEMA.md. Prices/model ids: models.json.
1. `cp keys.env.example keys.env` and fill it in (never commit it). `pip` extras: none (stdlib + requests).
2. Smoke test, zero network: `python3 run.py --dry-run --arm bare && python3 run.py --dry-run --arm mcp`
3. Real run: `python3 run.py --model <key in models.json> --arm bare|mcp [--limit N]`. Prints a cost estimate and refuses paid providers until you add `--confirm-spend` (`--max-usd X` caps spend mid-run).
4. Free local run: `python3 run.py --model local-gemma --arm mcp --limit 3` (uses whatever llama.cpp server is already on LOCAL_OPENAI_BASE; never starts one).
5. Runs are resumable: re-running the same command skips answered questions and retries errored ones; `--tag v2` starts a fresh run_id.
6. Grade: `python3 grade.py` sends every ungraded answer to the Syfert MCP `check_brief` tool (+ get_case for quote lookups); `--regrade` redoes all.
7. Report: `python3 report.py` writes results/report.md (per model/arm metrics + bare->mcp deltas); `--include-mock` shows dry-run rows.
8. Questions: data/questions.jsonl if present, else data/questions.sample.jsonl (6 hand-made rows); override with `--questions FILE`.
9. The grading rules (dedup, markdown stripping, quote lookup, abstain/warned heuristics) are in grade.py's docstring.
10. Everything lands in results/results.db (gitignored); runs.config_json records model id, prompts, max turns and prices used.
