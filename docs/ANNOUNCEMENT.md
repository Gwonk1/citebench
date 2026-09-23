# citebench: a public test of whether AI models cite real law

Since *Mata v. Avianca* in 2023, courts have repeatedly sanctioned lawyers for filing AI-invented or misdescribed citations. One public tracker now lists more than 1,300 U.S. decisions on the problem. There is still no repeatable public number for how often today's leading models do this.

citebench tries to provide one. It asked 11 widely used AI models legal research questions, each with a known answer: a real case that later courts cite for the stated rule. The headline results use the same 150 questions for every full-length run (77 Florida, 33 federal, 40 from ten other states); about one in ten answer cases has since been overruled or questioned, to test whether models notice.

Ten models answered on their own. Four answered with access to a free case-law search and citation-checking tool, on 55 to 150 questions. Every citation in every answer was then checked automatically against a database of 10.7 million U.S. opinions for three problems:

- the case does not exist (0.0% to 62.0% of citations without tools, 0.0% to 3.4% with them);
- the case exists but the name is wrong or a quoted passage is not in it (5.4% to 54.6% without tools, 1.9% to 5.7% with them);
- the case is real but has been overruled (0.0% to 4.6% without tools, 1.1% to 3.2% with them).

The best models rarely invent a case any more: Claude Fable 5.1, Claude Opus 5.5 and GPT-6 Astra did so for 0.4% of citations or less. Their problem is misquoting real ones, 5.4% to 7.4% of citations; about 60% of those "quotes" are accurate paraphrases put in quotation marks, and the rest are words the court never wrote.

With the tools, Claude Sonnet 5 misgrounded 1.9% of its citations and cited the expected case in 92.7% of answers, against 3.6% and 78.2% for the best frontier models without tools on the same 55 questions. Gemma 4 26B, running on one desktop GPU, misgrounded 2.8% with the tools against 5.4% for Opus 5.5 without them, though at this sample size those intervals overlap. The tools do not make every model beat every other on every measure: on invented cases, the top models are already under 1% on their own.

We also report how often a model declined to answer rather than guess (0.0% to 2.7% without tools, 0.0% with them), since an honest "I don't know" is a good outcome for a lawyer.

For Claude Fable 5.1, 14 of 755 citations could not be found by volume and page. 11 of them were real cases (10 distinct cases, all but one decided since 2018) that the database had but without their volume and page numbers. Those numbers are assigned by a private publisher, mostly West (Thomson Reuters), when it prints the case, and Florida's citation rule calls for them. Free citation checkers share this blind spot, so a real recent case and an invented one look the same to them; our checker now also matches the case name and year against the opinions themselves. The other 3 were not invented either: two real cases at the wrong page, and one real court order the checker misread.

Limits. The checking tool and the database are mine (I run syfert.com), and the tool-assisted arm uses the same tool, which is a conflict of interest. The automated checker makes mistakes. In my hand check of a random sample of its verdicts, it was right on 19 of 21 "quote not in the opinion" calls, 20 of 21 "quote found" calls and 6 of 6 wrong-name calls; the invented-case column has not been hand-checked yet. Legal AI products such as Harvey, Legora, Lexis+ AI and CoCounsel are not included because we could not obtain access on terms that allow an automated, published evaluation. A full run of everything cost $42.69 in API fees.

Results and methodology are at https://syfert.com/mcp/citebench/. The questions, code and every graded answer are public at https://github.com/Gwonk1/citebench. Any vendor can run the test on its own product and submit the results.

Graham Syfert
