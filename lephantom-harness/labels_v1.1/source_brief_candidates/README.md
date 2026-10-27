# Source-brief errors in LePhantomCite that the dataset does not label

The briefs behind LePhantomCite were written by human attorneys and carry their own mistakes. The dataset plants hallucinations
and scores only those, so a checker that catches a real, unplanted error is scored as a false positive. Syfert found the lists below
while running the benchmark in October 2026 and published them at https://www.syfert.com/lephantomcite/ (the HTML pages here are
those pages, saved 2026-10-27; the `.jsonl` files are the same rows, one JSON object per row, extracted from them).

The dataset authors verified the first list against the brief PDFs and Westlaw and adopted it as **v1.1** (Hugging Face commit
70aba90a, 2026-10-19: 41 source-brief errors labelled `optional`, 2 promoted to scored misquotes, 1 OCR fix). Everything else is
offered for their adjudication and for anyone scoring on this benchmark who wants to know what a "false positive" might really be.

| file | split | rows | what it is | reviewed? |
|---|---|---:|---|---|
| `quotes_train.jsonl` (`index.html`) | train | 43 | quotations altered inside quotation marks (41) or absent from the opinion (2) | hand-read; CourtListener phrase check; 42 adopted in v1.1, r160 declined by the authors |
| `citations_train.jsonl` (`citations.html`) | train | 42 | §1 wrong citation for the named case (9; r131 is garbled dataset text, not scored), §2 quoted passage 2+ pages from the pin (12), §3 off by one page (9), §4 proposition not on the pinned page (12) | §1–2 verified by hand; §3–4 unverified candidates |
| `model_flags_train130.jsonl` (`model.html`) | train130 | 12 | sentences a Claude Opus 5.5 + Syfert MCP run flagged that the gold does not mark, with hand verdicts (7 real, 3 plausible, 1 wrong, 1 not checked) | hand verdicts in the `header` field |
| `content_train_modeljudged.jsonl` (`content.html`) | train | 260 | cited sentences a model (Grok 4.7) judged "not supported" by the pinned page: 69 at confidence ≥ 0.92, 191 lower; partial pass (695 of 2,392 sentences) | NOT hand-reviewed; a strict reader calls ~40 % of real-brief sentences overstated, so treat as leads |
| `quotes_test_UNREVIEWED.jsonl` (`test.html`) | test | 51 | quotation candidates on the test split, generated blind by the same rules that produced the train list | nobody at Syfert has read these rows (test split kept sealed); for the authors |
| `citations_test_UNREVIEWED.jsonl` (`citations-test.html`) | test | 17 | citation / pincite candidates on the test split, generated blind by rules that reproduce the train hand sort | unread, as above |
| `model_flags_test_UNREVIEWED.jsonl` (`model-test.html`) | test | 57 | model flags on the test split the gold does not mark, with the model's own explanation | unread, as above |

Row fields: `status` (the review state of the whole file), `id` (`rNNN` train / `tNNN` test, file order of the v1.1 jsonl),
`section`, `header` (case, citation, and for the quote lists the CourtListener phrase result), then the labelled blocks of the page
(`brief`, `opinion`, `excerpt`, `checker`, `what_the_opinion_says_model`, ...), `notes` (diffs and CourtListener counts), `courtlistener`
(opinion link). Ids map to `../eval.jsonl` (test) and the dataset's `aux_train.jsonl` (train) by line order.

How the lists were made: Syfert's `check_brief` ran over every excerpt; findings that matched no gold span were triaged by hand on the
train split (quotes re-cut from the excerpt, compared word by word with the opinion text, phrase-checked on CourtListener's search).
The test split was never read: its three files were produced by scripts that encode the train hand sort and print counts only.
Prepared by Graham Syfert, syfert.com; corrections welcome by pull request or email.
