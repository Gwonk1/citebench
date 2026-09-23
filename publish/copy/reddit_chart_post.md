# Reddit post to accompany reddit_simple.png (g6 numbers, 2026-09-22)

**Title (r/legaltech):**
I tested 9 AI setups on 150 real legal citation questions. Frontier models rarely invent cases any more; they misquote real ones. Free retrieval tools fix most of it. [chart + open harness]

**Title (r/law):** Tested whether AI models cite real law correctly (150 questions, every cite checked against 10.7M opinions). Chart inside.

**Title (r/LawFirm):** I ran the "does the AI make up cases" test properly. Results are not what the sanctions orders suggest.

**Body:**

I'm a solo litigator in Florida. I run a free case-law site and a free MCP research connector, so read this with that conflict of interest in mind: I built both the tool being tested and the grader.

What I did: 300 legal propositions, each lifted from a real opinion so there is a known "gold" case, across Florida, federal, and ten other states. Each model was asked for the authority. Every citation in every answer was checked against a 10.7M-opinion corpus: does the case exist, is the name right, does the opinion actually contain the quoted words. Same 150 questions for every model on its own. Then the same models with the research tools attached.

What the chart shows (misquotes per 100 citations / found the right case per 100 questions):

- Claude Opus 5.5 on its own: 5 / 72. GPT-6: 7 / 58. Claude Fable 5.1: 8 / 73. Gemini 3.1 Pro: 23 / 63.
- Gemma 4 26B running on my own GPU: 52 / 3. Same model with the tools: 3 / 71.
- Opus 5.5 with the tools: 5 / 98. Fable with the tools: 3 / 95. Sonnet 5 with the tools: 2 / 93.

Invented, non-existent cases: 0 to 0.4 per 100 citations for every Claude and GPT row. The "fake case" problem is mostly gone at the top. What remains is quieter and worse for a brief: a real case, cited correctly, with a quote it does not contain. About 60% of those are accurate paraphrases in quotation marks; the rest are wrong wording, including one that reversed which party bore the burden under Celotex.

Two things I did not expect. First, my own free index could not resolve about 2% of the top models' real citations, because Southern Reporter pagination for post-2019 Florida cases is not in any free source. The methodology has a section on that. Second, the models with tools copied a citation error made by the Florida Supreme Court itself in 1984, because the tool served the court's text verbatim. The tool now flags those.

Caveats: 150 questions per bare row, 55 to 60 for most tool rows, so intervals are roughly plus or minus 5 to 8 points. I audited the grader by hand on 60 items; about 90% precision. Harvey, Legora, Lexis and Westlaw are not in the table because I could not obtain access on terms that allow an automated, published evaluation. The harness, questions, grader and raw reports are public; run it yourself and post your numbers.

Harness and data: https://github.com/Gwonk1/citebench
Full write-up: https://syfert.com/mcp/citebench/
