# not-unfair-legal-benchmark

This is the not-unfair legal benchmark. It challenges an agentic system on legal ability when that system is linked to a caselaw MCP.

The set was built unfairly, on purpose. The items are places the CourtListener corpus is deficient, and the gold is the corrected cite, the corrected court form, and the corrected text. A caselaw MCP that serves that corpus meets the same items, whichever agent is connected to it. A corpus that has already been corrected on that point passes the item.

It is a citation test and a bluebooking test.

## Citation

A citation item asks whether the connected caselaw returns the right case.

A real reporter cite that was never attached to the opinion comes back missing. A cite that was never a case comes back missing in the same words, so the set keeps both. A one-digit misprint is a miss when the neighbor is not named. An interior page is a miss when it does not resolve to the reported first page. Two clusters that share a cite are a miss when only one is named. A wrong caption on a real cite is a miss when the caption is accepted. The same cite sent twice, once under the right name and once under a wrong name, is a miss when the wrong name disappears and nothing says it does not match.

A denial of certiorari, an orders page, or a dismissal for want of a substantial federal question is a miss when the result presents that page as the lower court's own citation. Several of those pages are attached to the lower-court opinion and to the order at the same time. One Supreme Court page from 1981 is also attached to a 1996 court of appeals case.

A Westlaw or LEXIS cite is a miss when an official or regional reporter number exists for that case. Listing the vendor cite as a parallel counts. A Florida district court of appeal opinion stored as `Fla. L. Weekly Fed. D` is a miss. That is the federal weekly. The decision's reporter is the Southern Reporter, and the court is the numbered district.

A case that has been overruled, receded from, or depublished is a miss when the result presents it as ordinary authority. An unpublished opinion presented as published is the same kind of miss. A quotation is a miss when the opinion text still contains the garble that makes the quote fail.

Statutes and court rules are only partly in the set. Some are extracted and left unverified. A section that does not exist can be extracted and left standing. Some rule forms are not extracted at all.

## Bluebooking

A bluebooking item asks whether the court in the citation is the form a brief uses.

Florida district courts of appeal are `Fla. 1st DCA`, `Fla. 2d DCA`, `Fla. 3d DCA`, `Fla. 4th DCA`, `Fla. 5th DCA`, and `Fla. 6th DCA`. `Fla. Dist. Ct. App.` is a miss. `3rd` is a miss where the form is `3d`.

The other courts in the set are held to the same standard. A spelled-out state, a missing period or space, a bankruptcy appellate panel written as `Nth Cir. BAP`, a California court of appeal with a district written into the court name, an appellate court with no department or district, and an empty court cite are misses. `SCOTUS` is a miss for the Supreme Court. The Tax Court is `T.C.` The Court of International Trade is `Ct. Int'l Trade`. A Court of Criminal Appeals case filed as a court of appeals is a miss. The gold is the corrected court string.

## The same task for every system

Every item is a passage. Every system gets the same instruction and is graded on the words it sends back. A bare model, a model calling an MCP, and a tool called by itself are the same kind of arm.

The instruction is `PROMPT` in `grade.py`. The passage is `text` in `items/tasks.jsonl`. The gold is strings. A pass means the corrected cite or the corrected court form is in the answer. A miss means the answer repeats the bad form, rejects a real cite, stays silent on treatment, or adds a Westlaw or LEXIS cite beside a reporter cite.

`grade.grade(answer, gold)` returns that pass or miss. `grade.render(task)` is the full text to send. `python3 score_saved.py` grades the CourtListener replies already on disk. That arm is 32 passes and 153 misses, with 6 passages that were never saved as their own reply.

These rows are not in `tasks.jsonl`. The 1993 and 1994 Sixth DCA items are not that court. Five vendor rows are the same page, `136 S. Ct. 871`. `p07` is a candidate reporter number. One misprint overlay names the wrong page. A trailing space and two Florida circuit strings that are only `2nd` and `3rd` are not legal answers.

## Layout

The code is this directory, `citebench/not-unfair-legal-benchmark/`.

- `items/tasks.jsonl` is the set. 191 passages.
- `grade.py` is the instruction and the matcher.
- `items/pilot.jsonl`, `from_fixes.jsonl`, `bluebook.jsonl`, `courts.jsonl`, and `harder.jsonl` are the lookups the passages were built from. `build_tasks.py` rebuilds `tasks.jsonl`. `build_harder.py` rewrites `harder.jsonl`.
- `run.py` is the CourtListener arm. It sends one lookup per call and writes `results/<date>/<id>.txt`. It skips ids already on disk. Pace is one call, then 1.5 seconds.
- `clmcp.py` is the CourtListener runner. It reads `~/projects/.secrets/courtlistener.key` and sends `Authorization: Token`. The token is never printed. Read tools only. Do not call the alert or subscription tools.
- `score.py` reads a saved body into status, warning, cluster id, and statute lines.

```bash
python3 run.py items/pilot.jsonl --ids p10-rule
python3 report_wave.py results/20261021-courts items/courts.jsonl
```
