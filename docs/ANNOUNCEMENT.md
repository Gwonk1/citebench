# citebench: a public test of whether AI models cite real law

Since *Mata v. Avianca* in 2023, courts have repeatedly sanctioned lawyers for filing AI-invented or misdescribed citations. One public tracker now lists more than 1,300 U.S. decisions on the problem. There is still no repeatable public number for how often today's leading models do this.

citebench tries to provide one. It asks {n_models} widely used AI models 300 legal research questions, each of which has a known correct answer: a real case that later courts cite for the stated rule. About one in ten of those answer cases has since been overruled or questioned, to test whether models notice.

Each model answers every question twice: once on its own, and once with access to a free case-law search and citation-checking tool. Every citation in every answer is then checked automatically against a database of 10.7 million U.S. opinions for three problems:

- the case does not exist ({fabricated_bare}% of citations on average without tools, {fabricated_mcp}% with them);
- the case exists but the name is wrong or a quoted passage is not in it ({misgrounded_bare}% and {misgrounded_mcp}%);
- the case is real but has been overruled ({red_bare}% and {red_mcp}%).

We also report how often a model declined to answer rather than guess ({abstain_bare}% and {abstain_mcp}%), since an honest "I don't know" is a good outcome for a lawyer.

In the first completed run, 18 of the 20 citations our database could not find were real cases, 17 of them decided since 2018. The database had the opinions but not their volume and page numbers, which are assigned by a private publisher, mostly West (Thomson Reuters), when it prints the case, and which Florida's citation rule calls for. Free citation checkers share this blind spot, so a real recent case and an invented one look the same to them; our checker now also matches the case name and year against the opinions themselves.

Limits. The checking tool and the database are mine (I run syfert.com), and the tool-assisted arm uses the same tool, which is a conflict of interest. The automated checker makes mistakes; a human review of 50 of its verdicts found {grader_disagreements} disagreements. Legal AI products such as Harvey, Legora, Lexis+ AI and CoCounsel are not included because we could not get access that allows automated, published testing.

The questions, code and every graded answer are public at {repo_url}. Any vendor can run the test on its own product and submit the results.

Graham Syfert
