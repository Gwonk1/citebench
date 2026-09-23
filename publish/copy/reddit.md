<!-- Post only after the preliminary label is off the results page. Replace RESULTS_URL with https://syfert.com/mcp/citebench/ and REPO_URL with the public repository once it exists. -->

# r/legaltech

**Title:** I checked every citation from 11 AI models against 10.7M U.S. opinions. The best ones rarely invent cases now; they misquote real ones.

**Body:**

I'm a Florida litigator and I run syfert.com, a free case-law site with a citation checker. Conflict of interest up front: one arm of this test uses my tools, and the grader uses my database. The questions, grading rules and reports are public so you can check that.

**Setup.** 150 research questions (77 Florida, 33 federal, 40 from ten other states). Each asks for authority for a proposition that later courts cite a specific case for. Every citation in every answer is checked mechanically against 10.7 million U.S. opinions: does the case exist, does the name match, is the quoted language actually in the opinion, is it still good law.

**Results without tools (n = 150 questions each):**

- Claude Fable 5.1, Claude Opus 5.5 and GPT-6 Astra cited a nonexistent case 0.0% to 0.4% of the time (0/217 to 3/755 citations).
- But 5.4% to 7.4% of their citations were misgrounded: wrong case name or a "quote" not in the opinion. About 60% of those quotes (55/92) are accurate paraphrases inside quotation marks. The rest are words the court never wrote.
- Gemini 3.1 Pro: 4.1% invented (13/317), 22.7% misgrounded (72/317).

**With the tools:**

- Claude Sonnet 5: 1.9% misgrounded (5/265 citations, 55 questions), expected case found in 92.7% (51/55).
- Gemma 4 26B, running locally: 62.0% invented bare (171/276) to 0.7% with tools (2/289).

**One caveat about free databases.** Recent opinions often have no volume and page in free sources until a publisher prints them, so a real 2021 citation and a fake one both return "not found." The grader matches name and year first; for Fable that moved 11 of 755 citations from "not found" to "real." Both numbers are shown. Details: RESULTS_URL/methodology.html#s4

Not tested: Harvey, Legora, Lexis+ AI, CoCounsel. I could not obtain access on terms allowing a published automated evaluation.

The grader has an error rate. A hand check of its quote verdicts found "absent" right 19 of 21 times.

Results and methodology: RESULTS_URL

The harness is plain Python and a full run cost $42.69. I'd welcome anyone rerunning it, especially on a model or product I didn't test: REPO_URL

---

# r/law (title, 2 lines)

AI models have mostly stopped inventing cases. In a 150-question test, the best ones still misquoted or misnamed 5% to 7% of real citations.

# r/LawFirm (title, 2 lines)

Before you trust an AI's case quote: the best models invented under 0.5% of citations in my 150-question test,
but 5% to 7% had a quotation that isn't in the opinion or the wrong case name.
