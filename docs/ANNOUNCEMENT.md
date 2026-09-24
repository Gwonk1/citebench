# citebench: a public test of whether AI models cite real law

Since *Mata v. Avianca* in 2023, courts have repeatedly sanctioned lawyers for filing AI-invented or misdescribed citations. One public tracker now lists more than 1,300 U.S. decisions on the problem. There is still no repeatable public number for how often today's leading models do this.

citebench tries to provide one. It asked 11 widely used AI models legal research questions, each with a known answer: a real case that later courts cite for the stated rule. The headline results use the same 150 questions for every full-length run (77 Florida, 33 federal, 40 from ten other states); about one in ten answer cases has since been overruled or questioned, to test whether models notice.

Ten models answered on their own. Four answered with access to a free case-law search and citation-checking tool, on 55 to 150 questions. In a separate group, Claude Fable 5.1 and Claude Opus 5.5 also answered 60 questions through the Claude Code app with the same tool, alongside a Fable run through Claude Code without it as the control. Every citation in every answer was then checked automatically against a database of 10.7 million U.S. opinions (99 to 746 citations per model and arm) for three problems:

- the case does not exist (0.0% to 60.5% of citations without tools, 0.0% to 3.4% with them);
- the case exists but the name is wrong or a quoted passage is not in it (5.4% to 56.8% without tools, 1.9% to 5.7% with them);
- the case is real but has been overruled (0.0% to 4.6% without tools, 1.1% to 3.2% with them).

The best models rarely invent a case any more: Claude Fable 5.1, Claude Opus 5.5 and GPT-6 Astra had 0 to 2 "fabricated" citations each over 150 questions (2 of 746, 1 of 554, 0 of 217), and none of those three is a made-up case: two are real cases at the wrong page, and one is a real 2019 Michigan decision missing from my database. Their problem is misquoting real ones, 5.4% to 7.5% of citations; about 60% of those "quotes" are accurate paraphrases put in quotation marks, and the rest are words the court never wrote.

With the tools, Claude Sonnet 5 misgrounded 1.9% of its citations (5 of 264), against 3.6% (3 of 83) for the best frontier model without tools on the same 55 questions. Gemma 4 26B, running on one desktop GPU, misgrounded 2.8% with the tools (8 of 288) against 5.4% for Opus 5.5 without them (30 of 554), though at this sample size those intervals overlap. Through Claude Code, Fable 5.1 misgrounded 3.4% with the tools (13 of 387) and 9.9% without them (29 of 294) on the same 60 questions. The tools do not make every model beat every other on every measure: on invented cases, the top models are already under 1% on their own.

We also report how often a model declined to answer rather than guess (0.0% to 2.7% without tools, 0.0% with them), since an honest "I don't know" is a good outcome for a lawyer.

For Claude Fable 5.1, 13 of 746 citations could not be found by volume and page. 11 of them were real cases (10 distinct cases, all but one decided since 2018) that the database had but without their volume and page numbers. Those numbers are assigned by a private publisher, mostly West (Thomson Reuters), when it prints the case, and Florida's citation rule calls for them. Free citation checkers share this blind spot, so a real recent case and an invented one look the same to them; our checker now also matches the case name and year against the opinions themselves. The other 2 were not invented either: both are real cases at the wrong page.

Limits. The checking tool and the database are mine (I run syfert.com), and the tool-assisted arm uses the same tool, which is a conflict of interest. The automated checker makes mistakes. In my hand check of a random sample of its verdicts, it was right on 19 of 21 "quote not in the opinion" calls, 20 of 21 "quote found" calls and 6 of 6 wrong-name calls; the invented-case column has not been hand-checked yet. Legal AI products such as Harvey, Legora, Lexis+ AI and CoCounsel are not included because we could not obtain access on terms that allow an automated, published evaluation. A full run of everything cost $42.69 in API fees.

Results and methodology are at https://syfert.com/mcp/citebench/. The questions, code and every graded answer are public at https://github.com/Gwonk1/citebench. Any vendor can run the test on its own product and submit the results.

**Update 2026-09-23.** Two rows were added, run against the upgraded Syfert tool server (MCP v7), which adds find_authority and verify_quote, pinpoint pages in cite_as, and corrections in check_brief output.
Gemma 4 26B with MCP v7 (150 questions): 0.0% fabricated (0 of 171 citations), 1.2% misgrounded (2 of 171), expected case found in 90.0% (135 of 150).
Claude Opus 5.5 with MCP v7, through Claude Code (60 questions): 0.9% fabricated (2 of 231), 0.4% misgrounded (1 of 231), expected case found in 98.3% (59 of 60).
These two rows were graded with grader g8; the other published rows are unchanged from 2026-09-22 (grader g6). The g8 re-grade of every row is in the repository.

Graham Syfert
