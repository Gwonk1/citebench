_Generated 2026-10-17 08:34 by make_report.py from results/scores.json (paper matching rule; 95% bootstrap CIs over examples, 2000 resamples)._

| Arm | n | P % | R % | F1 % | P CI | R CI | F1 CI | repo-rule F1 | errors | cost $ (Claude Code: nominal, subscription) |
|---|---:|---:|---:|---:|---|---|---|---:|---:|---:|
| Syfert check_brief alone, strict mapping — no LLM; fabricated / name mismatch / absent quote | 390 | 34.1 | 13.0 | **18.8** | 26.5–41.8 | 9.6–16.5 | 14.3–23.2 | 18.6 | 0 | 0.00 |
| Syfert check_brief alone, broad mapping — strict + unresolved, near quotes, pin failures, proposition mismatch | 390 | 22.2 | 17.5 | **19.6** | 17.2–27.4 | 13.5–21.5 | 15.3–23.6 | 19.3 | 0 | 0.00 |
| Claude Code harness (subscription) Opus 5.5, non-agentic — claude -p, no tools; paper prompt | 390 | 76.0 | 68.0 | **71.8** | 71.1–80.9 | 63.2–72.7 | 67.7–75.6 | 69.7 | 0 | 10.11 |
| Claude Code harness (subscription) Opus 5.5, agentic + Syfert MCP (8 tools, 30 turns) — claude -p --strict-mcp-config; Claude Code's own system prompt/harness, not a raw API loop | 390 | 80.9 | 77.6 | **79.2** | 76.1–85.3 | 73.5–82.2 | 75.4–82.8 | 77.6 | 0 | 52.34 |
| Claude Code harness (subscription) Opus 4.8 (the paper's model), non-agentic — claude -p, no tools; tools as of mcp79 ff954bdd | 390 | 65.2 | 49.8 | **56.5** | 59.0–71.1 | 44.5–55.3 | 51.4–61.2 | 54.6 | 0 | 15.47 |
| Claude Code harness (subscription) Opus 4.8, agentic + Syfert MCP (8 tools, 30 turns) — same harness as the Opus 5.5 row; ran 21:40–~01:10 UTC 10-16/17 with tools as of mcp80 (driver 2c1084bb, lib 7f8a8c36) — NOT mcp79 despite the tag; mcp81 (quotes/pincites) was live 23:51–00:19 UTC (~examples 180–250) before its kill file restored mcp80 behaviour | 269 | 58.1 | 66.7 | **62.1** | 50.9–65.0 | 60.2–73.0 | 56.2–67.5 | 61.2 | 0 | 101.31 |
| Claude Code harness (subscription) Opus 5.5, agentic + Syfert MCP — tools as of mcp84 (10-17) — same harness and prompt as the 10-16 row; only the Syfert tools changed (mcp80–84) | 390 | 81.8 | 79.2 | **80.5** | 77.3–86.1 | 75.0–83.3 | 76.9–83.8 | 78.8 | 0 | 53.64 |
| Syfert check_brief alone, strict — tools as of mcp82 (10-17) — no LLM | 390 | 55.2 | 29.6 | **38.5** | 48.0–62.5 | 24.6–34.9 | 32.8–44.0 | 37.7 | 0 | 0.00 |
| Syfert check_brief alone, strict — tools as of mcp84b (10-17) — no LLM | 390 | 54.6 | 29.3 | **38.2** | 47.4–61.8 | 24.1–34.6 | 32.5–43.7 | 37.3 | 0 | 0.00 |
| Syfert check_brief alone, strict + near quotes / pin mismatches — tools as of mcp84b (10-17) — no LLM; mapping v2 | 390 | 52.4 | 32.3 | **40.0** | 45.5–59.2 | 27.0–37.5 | 34.4–45.5 | 39.1 | 0 | 0.00 |
| Claude Code harness (subscription) Opus 5.5, agentic + Syfert MCP (130-example subset) | – | not run | | | | | | | | |
| Gemma 4 E4B (Q4_0, local), non-agentic — thinking off, max_tokens 1500 | 390 | 9.5 | 17.8 | **12.4** | 6.7–12.7 | 12.4–23.2 | 8.8–16.0 | 12.5 | 0 | 0.00 |
| Gemma 4 E4B (Q4_0, local), agentic + Syfert MCP (4 tools, 15 turns) — thinking off; 8k context | 390 | 15.3 | 46.5 | **23.1** | 12.7–18.2 | 40.6–52.9 | 19.5–26.6 | 22.9 | 0 | 0.00 |

Paper (Liu, Stammbach, Henderson 2026, Table 2, same 390-example test split; ± = their reported half-widths):

| Paper arm | P % | R % | F1 % |
|---|---:|---:|---:|
| GPT-5 agentic (BOED, 30 steps) | 40.8 ± 4.3 | 84.4 ± 4.2 | 55.0 ± 4.2 |
| GPT-5 non-agentic | 36.9 ± 4.5 | 58.2 ± 5.2 | 45.2 ± 4.2 |
| Claude Code / Opus 4.8 agentic (WebSearch + CourtListener MCP) | 76.1 ± 5.6 | 62.8 ± 5.6 | 68.8 ± 4.6 |
| Qwen3.6-27B agentic | 28.9 ± 4.1 | 65.0 ± 5.1 | 40.0 ± 4.4 |
| Qwen3.6-27B non-agentic | 45.9 ± 7.8 | 31.5 ± 5.4 | 37.4 ± 5.7 |
| Gemini 2.5 Flash agentic | 16.9 ± 2.4 | 66.9 ± 5.1 | 27.0 ± 3.3 |
| GPT-OSS 120B agentic | 21.1 ± 3.2 | 55.1 ± 5.8 | 30.5 ± 4.0 |
| Qwen3-8B agentic | 12.0 ± 2.2 | 41.1 ± 6.0 | 18.6 ± 3.1 |

Per-error-type recall (% of required gold spans of that type matched; 'optional' spans excluded):

| Arm | Non-existent | Name mismatch | Pincite | Misquote | Content |
|---|---:|---:|---:|---:|---:|
| Syfert check_brief alone, strict mapping | 0.0 (0/31) | 50.0 (34/68) | 0.0 (0/55) | 19.6 (9/46) | 0.0 (0/131) |
| Syfert check_brief alone, broad mapping | 0.0 (0/31) | 60.3 (41/68) | 9.1 (5/55) | 26.1 (12/46) | 0.0 (0/131) |
| Claude Code harness (subscription) Opus 5.5, non-agentic | 100.0 (31/31) | 79.4 (54/68) | 23.6 (13/55) | 54.3 (25/46) | 77.9 (102/131) |
| Claude Code harness (subscription) Opus 5.5, agentic + Syfert MCP (8 tools, 30 turns) | 100.0 (31/31) | 85.3 (58/68) | 41.8 (23/55) | 84.8 (39/46) | 80.9 (106/131) |
| Claude Code harness (subscription) Opus 4.8 (the paper's model), non-agentic | 100.0 (31/31) | 72.1 (49/68) | 5.5 (3/55) | 37.0 (17/46) | 49.6 (65/131) |
| Claude Code harness (subscription) Opus 4.8, agentic + Syfert MCP (8 tools, 30 turns) | 100.0 (24/24) | 86.5 (45/52) | 27.3 (12/44) | 90.0 (36/40) | 43.2 (19/44) |
| Claude Code harness (subscription) Opus 5.5, agentic + Syfert MCP — tools as of mcp84 (10-17) | 100.0 (31/31) | 85.3 (58/68) | 49.1 (27/55) | 84.8 (39/46) | 81.7 (107/131) |
| Syfert check_brief alone, strict — tools as of mcp82 (10-17) | 96.8 (30/31) | 51.5 (35/68) | 0.0 (0/55) | 71.7 (33/46) | 0.0 (0/131) |
| Syfert check_brief alone, strict — tools as of mcp84b (10-17) | 96.8 (30/31) | 50.0 (34/68) | 0.0 (0/55) | 71.7 (33/46) | 0.0 (0/131) |
| Syfert check_brief alone, strict + near quotes / pin mismatches — tools as of mcp84b (10-17) | 96.8 (30/31) | 50.0 (34/68) | 12.7 (7/55) | 78.3 (36/46) | 0.0 (0/131) |
| Gemma 4 E4B (Q4_0, local), non-agentic | 29.0 (9/31) | 26.5 (18/68) | 27.3 (15/55) | 15.2 (7/46) | 7.6 (10/131) |
| Gemma 4 E4B (Q4_0, local), agentic + Syfert MCP (4 tools, 15 turns) | 71.0 (22/31) | 60.3 (41/68) | 25.5 (14/55) | 28.3 (13/46) | 48.9 (64/131) |
| _paper: GPT-5 agentic_ | 100.0 | 100.0 | 52.8 | 95.2 | 83.2 |
| _paper: Claude Code / Opus 4.8_ | 93.5 | 83.8 | 3.6 | 71.7 | 66.4 |
| _paper: Qwen3.6-27B agentic_ | 100.0 | 96.5 | 50.9 | 64.3 | 48.9 |

Pilots (20 train examples; measured tokens per example and the projection for 390 that gated each arm):

| Pilot | n | F1 % | tokens in / out / cache-read / cache-write per ex. | cost $ | projected 390 $ |
|---|---:|---:|---|---:|---:|
