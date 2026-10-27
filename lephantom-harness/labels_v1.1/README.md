---
license: cc-by-4.0

tags:
  - legal
  - hallucination
  - citation-verification
  - nlp
  - law
pretty_name: LePhantomCite
---

# Legal Phantom Citation Benchmark

**LePhantomCite** is a benchmarking dataset for evaluating AI systems on legal citation hallucination detection. It accompanies the paper [Who Checks the Citations? Benchmarking Legal Hallucination Detection](https://arxiv.org/abs/2606.21155) (Liu, Stammbach & Henderson, 2026).

---

## Dataset description

Legal citation hallucinations (fabricated or misrepresented case citations in court filings) are a growing problem as attorneys, judges, and pro se litigants increasingly rely on LLMs to draft legal documents. LePhantomCite provides a structured benchmark for evaluating automated citation verification systems designed to catch these errors before they reach a court.

The dataset contains 1,300 excerpts drawn from two sources:

- **1,000 excerpts** from real federal appellate briefs (filed 2012–2021, retrieved via CourtListener) with systematically injected hallucinations. Hallucinations are injected into 50% of segments (500 excerpts with hallucinations, 500 without), creating a balanced evaluation set.
- **300 entries** from the LLM-generated central holdings portion of [Dahl et al. (2024)](https://doi.org/10.1093/jla/laae003), manually verified against Westlaw.

### Typos in the source briefs

The briefs were written by human attorneys, and some of them contain human-made mistakes. These are not hallucinations we injected, so a checker that flags one may be scored as a false positive. We labelled the ones we found while building the dataset and review the ones reported to us since (see the [Changelog](#changelog)). We will continue to update and improve the dataset, but more such errors likely still remain.

If you find an error in a source brief or in our OCR text, please feel free to reach out to us! We will check the errors against the original brief PDF and the opinion on Westlaw, and release confirmed fixes as a new, tagged version of the dataset.


---

## Hallucination taxonomy

The dataset covers five hallucination types derived from real court filings:

| Type | Description | Example |
|---|---|---|
| **Non-existent citation** | Reporter citation does not correspond to any real case | `133 S. Ct. 1017` → `446 Cal. Rptr. 4th 183` |
| **Case name mismatch** | Case name and reporter citation refer to two different real cases | `Cinel v. Connick, 15 F.3d 1338` → `Boone v. Vinson, 15 F.3d 1338` |
| **Incorrect pincite** | Correct case, but the cited page number is wrong | `830 F.3d at 514` → `830 F.3d at 511` |
| **Verbatim misquote** | Quote is largely correct but does not appear verbatim in the cited case | One or two words replaced with synonyms |
| **Content misrepresentation** | Case exists but does not support the cited proposition | Holding altered to change its legal meaning |

---

## Data fields

Each entry contains:

| Field | Type | Description |
|---|---|---|
| `filename` | `string` | Excerpt ID. Brief excerpts are named `<case>_<CourtListener id>_part<N>.pdf`; holdings entries have numeric IDs |
| `text` | `string` | A short excerpt from a legal brief (or a holding statement), containing one or more case citations |
| `list_hallucinations` | `dict` | Hallucinated text span → hallucination type. Empty dict `{}` for entries without hallucinations. Spans labelled `optional` are errors in the source brief itself (see [Typos in the source briefs](#typos-in-the-source-briefs)) and are not scored |
| `list_hallucination_types` | `dict` | Citation → list of hallucination types attached to that citation. Missing for 24 `eval` entries that have no scored hallucinations; treat it as `{}` |
| `citations_in_segment` | `list[string]` | The case citations found in `text` |

Type labels: `non_existent_citation`, `case_name_mismatch`, `wrong_pincite`, `misquote`, `content_misrepresentation`, plus `optional`.

**Example entry** (from `eval`, text shortened):

```json
{
  "filename": "maher-terminals-llc-v-fmc_427555968_part15.pdf",
  "text": "[...] The court reviews the Commission’s interpretation of the Shipping Act pursuant to *Chevron U.S.A. v. Natural Res. Def. Council*, 467 U.S. 837 (1984), under which the court will defer to the Commission’s reasonable interpretation of a statutory provision, regardless of whether the text is ambiguous or unambiguous.\nThe Commission’s findings of fact are sufficient if supported by substantial evidence, that is, “such relevant evidence as a reasonable mind might accept as adequate to support a conclusion. ” *Consolo v.* Fed. Mar. Comm’n, 239 S.W.4th 88, 105 (D.N.J. 2020) (quoting Consol. Edison Co. v. NLRB, 599 So. 2d 195 (Fla. 3d DCA 1992)).",
  "list_hallucinations": {
    "The court reviews the Commission’s interpretation of the Shipping Act pursuant to *Chevron U.S.A. v. Natural Res. Def. Council*, 467 U.S. 837 (1984), under which the court will defer to the Commission’s reasonable interpretation of a statutory provision, regardless of whether the text is ambiguous or unambiguous.": "content_misrepresentation",
    "239 S.W.4th 88, 105 (D.N.J. 2020)": "non_existent_citation",
    "599 So. 2d 195 (Fla. 3d DCA 1992)": "case_name_mismatch"
  },
  "list_hallucination_types": {
    "467 U.S. 837 (1984),": [
      "content_misrepresentation"
    ],
    "599 So. 2d 195 (Fla. 3d DCA 1992)": [
      "case_name_mismatch"
    ],
    "239 S.W.4th 88, 105 (D.N.J. 2020)": [
      "non_existent_citation"
    ]
  },
  "citations_in_segment": [
    "599 So. 2d 195 (Fla. 3d DCA 1992)",
    "467 U.S. 837 (1984),",
    "239 S.W.4th 88, 105 (D.N.J. 2020)",
    "467 U.S. 837 (1984)",
    "463 U.S. 29, 43 (1983)",
    "477 F.3d 728, 732 (D.C. Cir. 2007)",
    "853 F.2d 958, 962 (D.C. Cir. 1988)"
  ]
}
```

---

## Hallucination type counts

| Hallucination Type | Train | Eval | Total |
|---|---|---|---|
| **Non-existent citation** | 126 | 32 | 158 |
| **Case name mismatch** | 126 | 63 | 189 |
| **Incorrect pincite** | 124 | 53 | 177 |
| **Verbatim misquote** | 127 | 42 | 169 |
| **Content misrepresentation** | 285 | 131 | 416 |
| **Total** | **788** | **321** | **1109** |

---

## Splits

The `aux_train` split is not used in the [paper](https://arxiv.org/abs/2606.21155) and may be noisier. We include it as a training resource for future projects.

| Split | Examples |
|---|---|
| `eval` | 390 |
| `aux_train` | 910 |

---

## Source data

Appellate briefs were collected from 13 U.S. Courts of Appeals via the [CourtListener API](https://www.courtlistener.com/), restricted to filings between January 2012 and December 2021 to minimize AI-generated content. Briefs were converted from PDF using [olmOCR](https://arxiv.org/abs/2502.18443), segmented with a fine-tuned RoBERTa sentence boundary model, and grouped into semantically coherent segments using Llama-3.3-70B-Instruct.

---


## Changelog

Each update is tagged in this repo; load a specific version with `load_dataset("ai-law-society-lab/Legal_Phantom_Citation", revision="v1.0")`. Source-brief errors confirmed against the cited opinion are added to `list_hallucinations` with the label `optional` (neither rewarded nor penalized), or occasionally under a regular type, in which case they are scored like planted errors. OCR mistakes are fixed in `text` directly. Every change is listed in [`updates/source_brief_errors.jsonl`](updates/source_brief_errors.jsonl).

---

## Citation

If you use LePhantomCite, please cite:

```bibtex
@article{liu2026checks,
  title   = {Who Checks the Citations? Benchmarking Legal Hallucination Detection},
  author  = {Liu, Patty and Stammbach, Dominik and Henderson, Peter},
  journal = {arXiv preprint arXiv:2606.21155},
  year    = {2026},
  url     = {https://arxiv.org/abs/2606.21155}
}
```

---

## License

This dataset is released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The source appellate briefs are public domain U.S. court documents. The LLM-generated holdings subset is derived from [Dahl et al. (2024)](https://doi.org/10.1093/jla/laae003) — please also cite that work if you use those entries.