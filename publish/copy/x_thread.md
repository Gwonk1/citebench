<!-- Post only after the preliminary label is off the results page. Replace https://syfert.com/mcp/citebench/ before posting. One number per tweet; attach the named chart PNG from publish/charts/. -->

1/8
I built citebench: every citation from 11 AI models, checked mechanically against 10.7 million U.S. opinions. All answered one shared set of legal research questions. Disclosure: I run syfert.com, and my tools are one arm of the test. Thread.

2/8
The best frontier models barely invent cases now. Claude Fable 5.1, Claude Opus 5.5 and GPT-6 Astra had 0 to 2 unresolvable citations each (2 of 746 for Fable), and none of those is a made-up case: real cases at the wrong page, or missing from my database.
[chart: fab_vs_misgrounded.png]

3/8
They misquote real ones instead. Fable 5.1 had a wrong case name, or a "quotation" that is not in the opinion, in 7.5% of its citations (56 of 746). Opus 5.5 and GPT-6 did only slightly better.

4/8
About 60% of those absent quotes (55 of 92) are accurate paraphrases someone put in quotation marks. The rest are words the court never wrote. In a brief, both are misquotes.

5/8
With the Syfert tools connected, Claude Sonnet 5 misgrounded 1.9% of citations (5 of 264, 55 questions), below every frontier model without tools on those questions (best: GPT-6, 3.6%, 3 of 83).
[chart: headline_bars.png]

6/8
A 26B model running on one desktop GPU (Gemma 4) invented 60.5% of its citations alone (159 of 263). With the tools: 0.7% (2 of 288), same 150 questions.
[chart: bare_vs_mcp.png]

7/8
Free case law has a blind spot: new decisions lack volume and page numbers until a publisher prints them, so real and fake both return "not found." Matching name and year moved 11 of 746 of Fable's citations to "real."
[chart: index_gap.png]

8/8
Not tested: Harvey, Legora, Lexis+ AI, CoCounsel; I could not obtain access on terms allowing a published automated evaluation. The whole study cost $42.69 in API fees. Rerun it: https://syfert.com/mcp/citebench/
