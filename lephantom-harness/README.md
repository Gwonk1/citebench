# LePhantomCite harness (Syfert's runs, reusable for any MCP)

This is the harness behind the LePhantomCite numbers Syfert has reported (see `results/results_table.md`). It runs the
benchmark "Who Checks the Citations? Benchmarking Legal Hallucination Detection" (Liu, Stammbach & Henderson, arXiv 2606.21155;
dataset `ai-law-society-lab/Legal_Phantom_Citation`) on three kinds of arm and scores every arm with the same matcher, so a
comparison across tools is like for like. Nothing in it is specific to Syfert except `run_syfert.py` (the no-model tool-alone arm)
and the default tool policy, which `--mcp-profile` replaces.

## What is here
- `labels_v1.1/` — the dataset's **v1.1 test labels** (`eval.jsonl`, 390 excerpts) and `source_brief_errors.jsonl`, the 42
  human typos in the source briefs that the authors accepted as label fixes in October 2026 (CC-BY-4.0; the dataset card is `README.md`
  in that folder). Score against v1.1 and say so; v1.0 scores are not comparable on the misquote and pincite types.
- `prep_data.py` — reads `labels_v1.1/eval.jsonl`, writes `data/test.jsonl` with stable ids `t000..t389` (file order). The id
  lists `data/subset130.txt` (a stratified third of the test set), `data/pilot20.txt` and `data/train130.txt` are shipped fixed.
- `lp_common.py` — the paper's prompts verbatim, the matching rule re-implemented from the paper and its public scorer
  (normalise, substring either way, `...` as an ordered-fragment wildcard; optional spans count as hits, never misses), the SQLite
  store (`results/lephantom.db`, one row per example per arm).
- `run_llm.py` — model arms. `--arm bare` is the paper's non-agentic prompt; `--arm mcp` is the agentic prompt plus a tool policy, with
  the tools served by an MCP server through headless Claude Code (`claude -p`, one subprocess per example, built-in tools removed,
  the server's tools pre-approved by exact name, no user settings or hooks). A raw Anthropic-API loop and a local llama-server loop exist
  too but are wired to the Syfert server only.
- `run_syfert.py` — the Syfert tool-alone arm: one `check_brief` call per excerpt, findings mapped to spans by fixed rules, no model.
  To add a tool-alone arm for another checker, write its own `run_<name>.py` that fills the same `preds` table.
- `score.py` — micro-averaged precision / recall / F1 per arm, 95 % percentile bootstrap CIs over examples (2,000 resamples,
  seed 20261016), per-type recall, and the "repo-rule" variant that treats optional spans as ordinary gold. `make_report.py` renders the table.
- `profiles/` — MCP profiles. `syfert.json` reproduces the default arm; `example_other_mcp.json` is the template for another server.

## Running another MCP through the same harness
1. Install Claude Code and sign in (the harness scrubs API keys from the subprocess environment; it runs on the subscription).
2. Write a Claude Code MCP config holding **only** your server, e.g. `profiles/yourserver_mcp.json`:
   `{"mcpServers":{"yourserver":{"type":"http","url":"https://.../mcp","headers":{"Authorization":"Bearer ..."}}}}`. Keep it out of git
   (`.gitignore` already covers `profiles/*_mcp.json`).
3. Copy `profiles/example_other_mcp.json` to `profiles/yourserver.json`: `name` = the key in your mcp config, `tools` = the exact tool
   names your server lists, `tool_policy_file` = a short text telling the model how to use those tools (the Syfert one is
   `profiles/syfert_policy.txt`; keep yours comparable in length and specificity, and publish it with your results).
4. Run both arms on the full test set:
   ```
   python3 prep_data.py
   python3 run_llm.py --model claudecode-opus --arm bare --split test --tag v11                       # model alone
   python3 run_llm.py --model claudecode-opus --arm mcp  --split test --tag v11 --prompt v1 --mcp-profile profiles/yourserver.json
   python3 run_llm.py --model claudecode-opus --arm mcp  --split test --tag v11 --prompt v1 --mcp-profile profiles/syfert.json   # same machine, same day
   python3 score.py && python3 make_report.py
   ```
   `--prompt v2`–`v4` add guidance that names Syfert `check_brief` fields; use them only with a profile whose policy file is written for
   them, or stay on `v1` for every arm you compare. `--max-turns 30` is the default for the mcp arm; say what you used.
5. Report P / R / F1 with the CIs, the label version (v1.1), the model id and Claude Code version, the date, and each arm's tool policy.
   Run the Syfert arm yourself on the same setup rather than quoting ours: Claude Code adds its own system prompt and harness,
   and model behaviour moves between versions.

## Caveats the paper's authors would want stated
- The model arms run inside Claude Code, not a raw API loop, so they are the paper's "Claude Code" row kind, not its API-agent kind.
- The paper's "reasoning field" sentence is dropped from the user prompt (it made Opus refuse); the rest of the prompt is verbatim.
- CIs are percentile bootstrap; the paper does not state its method.
- Cost figures from Claude Code are nominal (subscription).

## Licence
Code: MIT (this repository's LICENSE). `labels_v1.1/` is the authors' dataset under CC-BY-4.0 — cite the paper.
