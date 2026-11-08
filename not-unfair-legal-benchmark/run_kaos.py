# usage: venv313/bin/python run_kaos.py items/tasks.jsonl [--out results/20261103-kaos-raw]
#
# The raw kaos-citations arm (273 Ventures, Apache-2.0, PyPI kaos-citations 0.1.7): the package's public
# extract_citations() called by itself on each passage, no model in the loop, no network. The raw record
# list is saved per item (<out>/<id>.json) and the answer's last line is "ANSWER: ..." built only from
# the records' fields (the normalized citation of every record, in source order). The package has no
# court-name tool, no corpus and no verification, so a passage with no record gets "no answer from the
# tool" — the same rule render_syfert.render() applies to an empty Syfert body. Never reads gold.
import argparse, json, os, time
from kaos_citations import extract_citations
import kaos_citations

HERE = os.path.dirname(os.path.abspath(__file__))

def render(text, recs):
    out = [f"[kaos_citations.extract_citations {json.dumps(text)[:200]}]"]
    answers = []
    for r in recs:
        f = {k: r.get(k) for k in ("kind", "normalized", "volume", "reporter", "page", "pin_cite", "year", "court", "case_name", "subsequent_history") if r.get(k) not in (None, "", (), [])}
        out.append("record: " + json.dumps(f, default=str))
        if r.get("normalized"):
            answers.append(r["normalized"])
    out.append("ANSWER: " + ("; ".join(answers) if answers else "no answer from the tool"))
    return "\n".join(out)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("items"); ap.add_argument("--out", default=os.path.join(HERE, "results", "20261103-kaos-raw"))
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    rows = [json.loads(l) for l in open(a.items)]
    with open(os.path.join(a.out, "server.json"), "w") as f:
        json.dump({"package": "kaos-citations", "version": getattr(kaos_citations, "__version__", "?"), "date": time.strftime("%Y-%m-%d %H:%M:%S %Z")}, f, indent=2)
    t0 = time.time(); n_err = 0
    with open(os.path.join(a.out, "answers.jsonl"), "w") as fa:
        for row in rows:
            try:
                recs = [c.model_dump() for c in extract_citations(row["text"])]
                err = None
            except Exception as e:
                recs, err = [], repr(e); n_err += 1
            body = {"id": row["id"], "class": row["class"], "records": recs, "error": err}
            with open(os.path.join(a.out, row["id"] + ".json"), "w") as f:
                f.write(json.dumps(body, indent=1, default=str) + "\n")
            fa.write(json.dumps({"id": row["id"], "answer": render(row["text"], recs)}) + "\n")
    print(f"{len(rows)} items, {n_err} errors, {time.time()-t0:.2f}s total")

if __name__ == "__main__":
    main()
