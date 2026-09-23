# citebench: methodology

citebench measures one thing: when a frontier language model is asked for legal authority, how often are its citations real, correctly named, faithfully quoted and still good law. It is built by Graham Syfert, a Florida plaintiff's litigator who runs syfert.com and the Syfert legal MCP server. That is a conflict of interest: one arm gives models the Syfert tools, and the grader uses the same corpus. Section 6 addresses it.

## 1. Why this benchmark exists

Good research on legal hallucination exists, but there is no number a practitioner can reproduce next month against current frontier models, graded against a full case-law corpus rather than by hand.

**Prior academic work.** Dahl, Magesh, Suzgun and Ho, "Large Legal Fictions: Profiling Legal Hallucinations in Large Language Models," *Journal of Legal Analysis* 16:64-93 (2024), asked public models verifiable questions about randomly selected federal cases and found that they "hallucinate at least 58% of the time," with GPT-4 at the low end and Llama 2 at up to 88% (https://academic.oup.com/jla/article/16/1/64/7699227; preprint https://arxiv.org/abs/2401.01301; code https://github.com/reglab/legal_hallucinations). Those models are several generations old.

Magesh, Surani, Dahl, Suzgun, Manning and Ho, "Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools" (arXiv May 2024; *Journal of Empirical Legal Studies* 2025), ran 202 preregistered queries against Lexis+ AI, Westlaw AI-Assisted Research, Ask Practical Law AI and GPT-4, and found that Lexis+ AI and Westlaw AI-Assisted Research hallucinated between 17% and 33% of the time (https://arxiv.org/abs/2405.20362; https://onlinelibrary.wiley.com/doi/full/10.1111/jels.12413). That paper introduced the distinction this benchmark borrows: a response is *misgrounded* when "key factual propositions are cited but the source does not support the claim," which the authors count as a hallucination alongside plain factual error. The same paper notes that Thomson Reuters denied the team access three times before the initial release, and that the vendors' terms restricted programmatic access. Both studies relied on expert hand-coding: careful, but not cheaply repeatable.

**The courts.** In *Mata v. Avianca, Inc.*, 678 F. Supp. 3d 443 (S.D.N.Y. June 22, 2023), Judge Castel sanctioned two lawyers and their firm $5,000 for filing ChatGPT-invented decisions (https://caselaw.findlaw.com/court/us-dis-crt-sd-new-yor/2335142.html). In May 2025 a special master in *Lacey v. State Farm General Insurance Co.* (C.D. Cal. No. 2:24-cv-05205) imposed $31,100 on two firms after about 9 of 27 citations in a brief proved wrong, at least two of them nonexistent (https://reason.com/volokh/2025/05/13/ai-hallucination-in-filings-involving-14th-largest-u-s-law-firm-lead-to-31k-in-sanctions/). In *Johnson v. Dunn*, 792 F. Supp. 3d 1241 (N.D. Ala. July 23, 2025), the court disqualified three Butler Snow lawyers from the case and referred them to their state bars after finding ChatGPT-generated false citations, reasoning that fines were not deterring the conduct (https://www.courthousenews.com/johnson-vs-dunn-attorney-sanctions-order/). On February 18, 2026, the Fifth Circuit in *Fletcher v. Experian Information Solutions, Inc.*, No. 25-20086, ordered appellant's counsel to pay $2,500 for a reply brief containing quotations, citations and assertions the cited cases did not support (https://www.ca5.uscourts.gov/opinions/pub/25/25-20086-CV0.pdf). Damien Charlotin's database of court decisions finding reliance on hallucinated material listed 2,046 decisions, 1,397 of them in the United States, when retrieved on 2026-09-22 (https://www.damiencharlotin.com/hallucinations/).

*Fletcher* and *Lacey* are not only about invented cases; several errors were real cases cited for things they do not say. Checking existence alone misses that half of the problem.

**Industry benchmarks.** Neither of the two best-known industry efforts produces this number.

- Harvey's BigLaw Bench (August 2024) scores models on tasks drawn from lawyer billing entries, with an "answer score" (what share of lawyer-quality work product the model completes) and a "source score" (what share of correct statements the model supports with an accurate source) (https://www.harvey.ai/blog/introducing-biglaw-bench). It does not check model-generated case citations against a case-law corpus, and the public repository holds samples only; the full dataset is available by contacting Harvey (https://github.com/harveyai/biglaw-bench). Harvey's Legal Agent Benchmark (LAB), open-sourced May 6, 2026, measures long-horizon agent work product against expert-written rubrics (https://www.harvey.ai/blog/introducing-harveys-legal-agent-benchmark). Neither reports a fabricated-citation rate.
- Vals AI's first Legal AI Report (February 27, 2025) covered document tasks such as extraction, summarization, redlining and EDGAR research, and expressly left legal research out (https://www.vals.ai/industry-reports/vlair-2-27-25). Its legal research report (October 14, 2025) had lawyers and law librarians grade 200 questions answered by Alexi, Counsel Stack, Midpage, ChatGPT and a lawyer baseline on accuracy, authoritativeness and appropriateness (https://www.vals.ai/industry-reports/vlair-10-14-25). Citation validity is folded into authoritativeness rather than reported as a rate, and grading is by hand.

citebench is narrower. It does not ask whether an answer is good legal work, only whether each citation is real, correctly named, faithfully quoted and still good law, and it grades mechanically so anyone can rerun it.

## 2. Task design

**Questions.** The set has 300 questions. Each is built from one row of a propositions store: a statement of law that later courts have cited a specific opinion for, with that opinion recorded as the gold case. Each question records the state (or "us" for federal), the court, the proposition, the gold case's cluster ID, Bluebook citation, name, decision date and treatment flag, and the source row for provenance. The prompt looks like this:

> You are assisting a Florida litigator. Cite the controlling authority for this proposition, with a pinpoint if you can: <proposition>. Give the case name, reporter citation, court and year. If you are not certain a citation is real, say so instead of guessing.

**Choosing gold cases.** Each gold case is the opinion that later courts cite for the proposition, as recorded in the propositions store, so the answer key reflects how courts use the case. [Placeholder: sampling frame, per-state quotas, court-level mix, date range and deduplication rules, from the question-builder config when the set is frozen. Mix: {n_states} jurisdictions, {pct_federal}% federal.] The gold case is a reference point, not the only right answer. A model that cites a different real case that supports the proposition is not penalized on the integrity metrics; it simply does not score a gold hit.

**Deliberate bad-law gold cases.** About 10% of questions (target 30) use a gold case whose treatment flag is red (overruled or abrogated) or yellow (questioned). These are the questions where a model that remembers a famous case will cite something a careful lawyer would not. They are reported as their own slice. [Design note: the results schema does not yet record whether an answer warned the user about negative treatment. Until that field exists, the bad-law slice is reported with red_rate and gold_recall only, and a gold hit on a red gold case is not counted as a success.]

**Two arms.** Each model answers every question twice.

- *bare*: the prompt alone, no tools, no retrieval.
- *mcp*: the same prompt, with the Syfert MCP tools available (search_cases, get_case, check_citation, check_brief, get_treatment, get_propositions, get_citing_cases, search_quotes, find_issues and related tools). Tool use is up to the model and is logged.

The bare arm measures what a lawyer gets from a chat window. The mcp arm measures whether a corpus-backed citator changes that.

**Why abstention is scored.** The prompt invites the model to say it is not sure. A model that gives no citation cannot give a fabricated one, so the citation-level rates would reward silence if reported alone. abstain_rate is reported next to every other metric so that a low fabricated_rate bought by refusing half the questions is visible. For a lawyer an honest "I don't know" is far cheaper than a confident fake, so abstention is a separate disclosed outcome, not a failure.

## 3. Grading

Every answer in both arms goes through check_brief, the Syfert MCP tool that extracts each citation, resolves it against the corpus, compares the claimed name to the resolved case, looks for quoted passages in the opinion text, and reports the treatment flag. Raw output is stored with each grade.

Three kinds of bad citation are kept separate:

- **Fabricated.** The citation does not resolve to any opinion in the corpus. The case does not exist, or the reporter volume and page point nowhere. A citation the reporter index cannot resolve is first matched by case name and year against the opinions, or found cited at that page by later courts; a match is counted as real but unindexed, not fabricated (section 4).
- **Misgrounded.** The citation resolves to a real opinion, but either the claimed name does not match the opinion at that citation (name mismatch), or a passage the answer presents as a quotation is not in that opinion (quote absent). This follows the Magesh et al. concept but is narrower: the grader detects a mismatched name or an invented quote, not a real, correctly named case cited without quotation for a proposition it does not support. That subtler failure is only partly captured, through gold_recall.
- **Stale.** The citation is real and correctly named, but the case is flagged red (overruled or abrogated) or yellow (questioned) by Syfertize treatment.

**Metrics**, per (model, arm). Counts are summed over all questions before dividing, so a question with many citations weighs more than one with few.

| Metric | Definition |
|---|---|
| fabricated_rate | total fabricated citations / total citations |
| misgrounded_rate | (total name mismatches + total absent quotes) / total citations |
| red_rate | total citations to red-flagged cases / total verified citations |
| gold_recall | share of questions whose answer cites the gold case |
| abstain_rate | share of questions answered with no citation and an express statement of uncertainty |

Yellow counts are reported beside red_rate but not folded into it, because "questioned" ranges from one critical footnote to a serious split. Name mismatch is classed as misgrounding because the reporter citation is real; some are really fabrications that landed on a real page, and the per-answer records let readers reclassify them.

**The grader has an error rate.** check_brief can fail to parse a citation form, fail to resolve a real citation, or miss a quote because of text differences. [Placeholder: results of a human audit of 50 randomly sampled grader verdicts, stratified across fabricated, misgrounded, stale and clean, reporting the number of verdicts a lawyer reviewer disagreed with and in which direction. Auditor: {auditor}. Agreement: {x}/50.]

## 4. Why real citations go unresolved: the reporter pagination moat

In the first full run, Claude Fable 5.1 gave 755 citations in 150 answers; the reporter index could not resolve 20. Matched by case name and year to opinions in the corpus, 18 citations (14 distinct cases, 2.4% of all citations) were real. The other 2 were real cases cited at the wrong place: *Jaffy v. Jaffy* is at 965 So. 2d 825, not 1245, and *Wilcoxon v. Moller* is 132 So. 3d 281 (Fla. 4th DCA 2014), not 132 So. 2d 5 (Fla. 1961). The 18 include *Conage v. United States*, 346 So. 3d 594 (Fla. 2022); *Advisory Opinion to the Governor re Implementation of Amendment 4*, 288 So. 3d 1070 (Fla. 2020); *Ham v. Portfolio Recovery Associates*, 308 So. 3d 942 (Fla. 2020); *Bush v. State*, 295 So. 3d 179 (Fla. 2020); *In re Caden C.*, 11 Cal. 5th 614 (2021); *Columbia Memorial Hospital v. Hinds*, 38 N.Y.3d 253 (2022); and *Berbridge v. Sam's East, Inc.*, 728 F. App'x 929 (11th Cir. 2018). The corpus holds each opinion's text, from CourtListener, but not its volume and page. Seventeen of the 18 were decided from 2018 to 2022. The other, *Schultz v. Boy Scouts of America, Inc.*, 65 N.Y.2d 189 (1985), is an ordinary index gap.

**Who assigns the numbers.** The Southern Reporter and the other regional reporters belong to West's National Reporter System, published by Thomson Reuters (https://store.legal.thomsonreuters.com/en-us/products/southern-reporter-3d-full-set-40739988), as did the Federal Appendix until 2021 (https://en.wikipedia.org/wiki/Federal_Appendix). Some official reports are privately published too: California's by LexisNexis (https://store.lexisnexis.com/en-us/caofficialreports), New York's by Thomson Reuters under state contract (https://nycourts.gov/reporter/files/annual2021.pdf) [seen through a search index only; the site refused direct fetch]. As Free Law Project puts it, "until the content is in a book, there's no volume or page to cite to" (https://free.law/2026/04/16/scanning-americas-case-law/).

**Florida requires those numbers.** Fla. R. App. P. 9.800 "applies to all legal documents, including court opinions." It cites Florida Supreme Court decisions from 1887 on to the Southern Reporter. Only for a case "not published in Southern Reporter" does it allow Florida Law Weekly, a subscription product (https://www.floridalawweekly.com/), and then a slip opinion with an optional Westlaw or LEXIS number (https://flcourts-media.flcourts.gov/content/download/865220/file/Appellate-Court-Rules-10-01-22-1.pdf). A June 11, 2026 amendment changed only docket number formats (https://flcourts-media.flcourts.gov/content/download/2489908/opinion/Opinion_SC2025-0241.pdf). About 20 states assign public-domain citations themselves (Free Law Project, above). A University of South Carolina guide based on AALL's Universal Citation Guide lists 17, including Wisconsin, Oklahoma, North Dakota, Montana, New Mexico, Ohio and Illinois (https://guides.law.sc.edu/universalcitation/adoptedby). Illinois, for one, has assigned the citation and paragraph numbers at filing since July 1, 2011 (https://www.isba.org/barnews/2011/05/31/illinois-supreme-court-announces-new-public-domain-citation-system-ending-era-of-printed-volumes). There an opinion is citable the day it issues; in Florida the preferred citation comes only from a publisher.

**Not copyrighted, still gated.** Affirming a preliminary injunction, *West Publishing Co. v. Mead Data Central, Inc.*, 799 F.2d 1219, 1223 (8th Cir. 1986), held that "the pagination of West's volumes reflects and expresses West's arrangement" and that LEXIS's planned star pagination infringed. *Matthew Bender & Co. v. West Publishing Co.*, 158 F.3d 693 (2d Cir. 1998), disagreed: the volume and page numbers "are not original components of West's compilations and are not themselves protected by West's compilation copyright," so star pagination does not infringe; it declined to follow *Mead* after *Feist*. But a number anyone may copy must first be published somewhere: for a new decision, in the publisher's products or a later opinion citing the case by page.

**The free sources stop.** The Caselaw Access Project's scanned volumes end at 275 So. 3d (2018 to 2019), 714 F. App'x (2018) and 29 N.Y.3d (2017), per its own metadata (https://static.case.law/so3d/VolumesMetadata.json; same file under f-appx and ny3d). [A Library of Congress guide says "through 2020" (https://guides.loc.gov/free-case-law/caselaw-access-project).] Commercial-use limits from the Ravel/LexisNexis agreement expired in March 2024 (https://lil.law.harvard.edu/blog/2024/03/26/transitions-for-the-caselaw-access-project/). CourtListener scrapes new opinions from court websites and so "does not get the official pagination or citations for the decisions." In April 2026 Free Law Project began scanning printed reporters to fill "the gap between when the Harvard data ends, in 2018, and today" (post above). Until then, the free route is a later citing opinion; for 12 of the 18, our grader found later courts citing the same volume and page.

**Consequence for citation checking.** CourtListener's citation lookup, like our index, keys on volume and page and answers a miss with "Citation not found" (https://wiki.free.law/c/courtlistener/help/api/rest/v4/citation-lookup). For a decision newer than the free pagination, a real citation and an invented one get the same answer. This window opens where the scanned volumes stop and closes case by case; it has no fixed length. Free data can close it by matching the claimed name and year to an opinion in the corpus. citebench's grader does this, logging the evidence, and so has syfert.com's Brief Check since 2026-09-22. A name match does not confirm the page: a real name with an invented page past the index still passes. The headline fabricated_rate counts only unmatched citations (0.3% here); fabricated_strict_rate counts every citation the index cannot resolve (2.6%).

## 5. What is not tested, and why

Harvey, Legora, Lexis+ AI and Westlaw CoCounsel are not in the results. They are enterprise products sold under negotiated agreements, we could not obtain access on terms that allow an automated, published evaluation, and the standard terms we could read do not permit a harness like this one. Harvey's Evaluation Terms of Service (last updated January 9, 2026) say a user may not "attempt automated means to scrape content or Output from the Service" (https://www.harvey.ai/legal/evaluation-terms-of-service). Legora's US General Terms and Conditions bar using "any automated or programmatic method to extract data or Output from the Services other than such methods provided by Legora" and using access "to build a product or service which competes with the Services" (https://legora.com/legal/us-general-terms-and-conditions). Magesh et al. report that the LexisNexis terms in force in 2023 prohibited programmatic access (https://arxiv.org/abs/2405.20362). [We did not find language in Harvey's or Legora's public terms that expressly prohibits publishing benchmark results, and we do not claim one exists. Negotiated customer agreements may differ and are not public.]

The harness is public. Any vendor, including those four, can run it against its own product and submit results with the raw answers and grades; they will be published marked as vendor-run.

Also out of scope: statute and rule citations (check_brief checks them; this version reports case citations only), the correctness of the legal analysis, pinpoint accuracy, and non-U.S. law.

## 6. Threats to validity

**Same corpus for gold set and grader.** A systematic corpus error affects both question and answer key. The mcp arm is also partly circular: a model that calls check_citation before answering is using the grader's own tool. A lawyer using the tool gets the same benefit, but the bare-versus-mcp gap is "value of this toolset as graded by this toolset," not a neutral measure.

**Coverage gaps can turn a real cite into a "fabricated" one.** The corpus holds about 10.7 million U.S. opinions, built from CourtListener and Caselaw Access Project data, and no free corpus is complete. Recent opinions often lack reporter pagination; section 4 explains why and how the grader compensates. Decisions cited only by Westlaw or Lexis number may not resolve, and some trial-level and older material is thin. For opinions from 2020 on, most corpus text comes from court PDFs converted to plain text, where hyphenation and encoding artifacts can hide a real quotation. Every citation graded fabricated will be listed so readers can check it elsewhere. [Placeholder: fabricated verdicts manually confirmed against a second source: {n_confirmed}/{n_fabricated}.]

**Contamination.** syfert.com pages are public and crawlable. Models may have been trained on them, which could help them in both arms. The question prompts are generated from propositions, not copied from page text, but a proposition may appear nearly verbatim on a case page. Published question sets also leak. [Proposal, not yet decided: hold back a private rotating slice and report whether results on it differ.]

**Prompt sensitivity.** Results depend on the template, and the explicit permission to abstain probably lowers fabrication. [Placeholder: sensitivity run on a 50-question subset with two alternative templates, one without the abstention sentence.]

**Sample size.** 300 questions is enough to separate large differences and not small ones. For question-level proportions (gold_recall, abstain_rate) we report Wilson 95% intervals; at n = 300 the half-width is about 5.7 points near 50% and about 3.4 points near 10%. For the citation-level rates, citations within one answer are not independent, so intervals come from a bootstrap that resamples questions (10,000 resamples). Comparisons between arms of the same model are paired by question. With five models and five metrics, readers should expect some nominally significant differences by chance; we will not rank models on differences whose intervals overlap.

**Non-determinism and drift.** Hosted models change without notice and sample stochastically. Each run records model ID, date and settings in runs.config_json; a result describes that model on that date.

## 7. Reproduction

**Keys.** API keys go in `keys.env` at the repository root (gitignored). You need a model-provider key (the reference run uses OpenRouter) and a Syfert MCP token for the mcp arm and grading. [Placeholder: exact variable names once the harness is frozen.]

**One command.** [Placeholder: final command name.]

```
citebench run --models models.yaml --arms bare,mcp --confirm-spend
```

The harness prints an itemized cost estimate and refuses to make paid API calls without `--confirm-spend`. Results go to `results/results.db` (tables runs, answers, grades), from which every published number can be recomputed.

**Cost.** Prices below are OpenRouter list prices per million tokens, retrieved 2026-09-22 from https://openrouter.ai/api/v1/models. The reference model set is a placeholder until the run is frozen.

| Model (OpenRouter ID) | Input $/M | Output $/M |
|---|---|---|
| openai/gpt-5.6-terra | 2.00 | 12.00 |
| anthropic/claude-opus-5.5 | 4.00 | 20.00 |
| google/gemini-3.1-pro-preview | 2.00 | 12.00 |
| moonshotai/kimi-k3 | 3.00 | 15.00 |
| qwen/qwen3.8-max-0902 | 2.00 | 6.00 |

Five models, two arms and 300 questions is 3,000 conversations. A light run (bare: about 300 input and 600 output tokens per question; mcp: about 6,000 in and 1,000 out, since tool results are re-sent each turn) costs about $56. A heavy run (bare 400/1,500 with reasoning tokens; mcp 15,000/2,000) costs about $128. The mcp arm is 70 to 80 percent of the cost; batch pricing, where offered, roughly halves it. The harness records actual cost per answer, and we will publish the real figure. Grading runs through the Syfert MCP and is subject to its rate limits, not per-token billing.
