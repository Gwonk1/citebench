# usage: python3 run_syfert.py items/tasks.jsonl [--out results/20261026-syfert-raw] [--ids a,b] [--render-only]
#
# The raw Syfert MCP arm: one Syfert MCP tool called by itself on each passage, no model in the loop.
# A deterministic router picks the tool from the item class and the passage shape, the raw tool body is
# saved per item (<out>/<id>.json), and render_syfert.render() turns that body into an answer whose last
# line is "ANSWER: ..." built only from tool fields. The router and renderer read class and text, never
# gold or evidence. Skips ids already on disk; --render-only rebuilds answers.jsonl from the saved bodies.
# Pace: one call at a time, at least 1.5 s apart (syfmcp.MIN_GAP), so under 40 calls a minute.
import argparse
import json
import os
import re
import time

import render_syfert

HERE = os.path.dirname(os.path.abspath(__file__))

# A reporter citation: volume, reporter, first page ("595 F.3d 151", "10 F. App'x 657", "2003 WL 23353478").
CITE = re.compile(r"\b(\d{1,4})\s+([A-Z][A-Za-z.'’ ]{0,30}?\d?[a-z]{0,2}\.?)\s+(\d{1,7})\b")
COURT_PROMPTS = (
    re.compile(r"^Give the Bluebook abbreviation for this court:\s*(.+?)\.?\s*$", re.S),
    re.compile(r"^Correct this court abbreviation to Bluebook form:\s*(.+?)\s*$", re.S),
    re.compile(r"^Give the Bluebook court abbreviation for (?:the )?(.+?)\.(?:\s|$)", re.S),
)


def court_query(text):
    """The court name / abbreviation a bluebook court prompt asks about, or None (the passage is a citation)."""
    t = text.strip()
    for rx in COURT_PROMPTS:
        m = rx.match(t)
        if m:
            return m.group(1).strip()
    return None


def split_case(text):
    """(case_name, citation) from a passage like 'Name v. Name, 595 F.3d 151.' Either may be ''."""
    t = text.strip()
    m = CITE.search(t)
    if not m:
        return "", ""
    cite = m.group(0).strip()
    name = t[:m.start()].strip().rstrip(",").strip()
    name = re.sub(r"^(See|see|Give the citation for)\s+", "", name)
    return name, cite


def route(row):
    """-> (tool, args). Reads class and text only."""
    klass, text = row["class"], row["text"]
    if klass == "bluebook":
        q = court_query(text)
        if q:
            return "find_court", {"name": q}
        return "check_brief", {"text": text}
    if klass == "treatment":
        name, cite = split_case(text)
        args = {"citation": cite, "compact": True}
        if name:
            args["case_name"] = name
        return "get_treatment", args
    return "check_brief", {"text": text}


def fetch(row):
    import syfmcp
    tool, args = route(row)
    calls = []
    try:
        calls.append(syfmcp.call(tool, args))
    except Exception as e:  # transport / JSON-RPC failure: saved, rendered as no answer
        calls.append({"tool": tool, "args": args, "is_error": True, "text": "ERROR " + str(e)[:500], "json": None})
    if tool == "check_brief" and not render_syfert.brief_has_cites(calls[0].get("json")):
        # Fallback only when check_brief extracts nothing: check_citation on the passage.
        name, cite = split_case(row["text"])
        ca = {"citation": row["text"].strip()[:500]}
        if name and cite:
            ca = {"citation": cite, "expected_case_name": name}
        try:
            calls.append(syfmcp.call("check_citation", ca))
        except Exception as e:
            calls.append({"tool": "check_citation", "args": ca, "is_error": True, "text": "ERROR " + str(e)[:500], "json": None})
    return {"id": row["id"], "class": row["class"], "calls": calls}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("items")
    ap.add_argument("--out", default=os.path.join(HERE, "results", "20261026-syfert-raw"))
    ap.add_argument("--ids", default="")
    ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()
    want = [x for x in args.ids.split(",") if x]
    out = args.out
    os.makedirs(out, exist_ok=True)
    rows = [json.loads(l) for l in open(args.items) if l.strip()]
    if want:
        rows = [r for r in rows if r["id"] in want]
    if not args.render_only:
        import syfmcp
        info = syfmcp.server_info()
        with open(os.path.join(out, "server.json"), "w") as f:
            f.write(json.dumps({"serverInfo": info, "url": syfmcp.URL, "date": time.strftime("%Y-%m-%d %H:%M:%S %Z")}, indent=2) + "\n")
        print("server", info.get("name"), info.get("version"))
        for row in rows:
            dest = os.path.join(out, row["id"] + ".json")
            if os.path.exists(dest):
                print("skip", row["id"])
                continue
            body = fetch(row)
            with open(dest, "w") as f:
                f.write(json.dumps(body, indent=1) + "\n")
            print("wrote", row["id"], " ".join(c["tool"] for c in body["calls"]),
                  "err" if any(c["is_error"] for c in body["calls"]) else "")
    # Render every saved body for the rows asked for (all rows when no --ids).
    n = 0
    with open(os.path.join(out, "answers.jsonl"), "w") as f:
        for row in [json.loads(l) for l in open(args.items) if l.strip()]:
            if want and row["id"] not in want:
                continue
            src = os.path.join(out, row["id"] + ".json")
            if not os.path.exists(src):
                continue
            body = json.load(open(src))
            f.write(json.dumps({"id": row["id"], "answer": render_syfert.render(row, body)}) + "\n")
            n += 1
    print("rendered", n, "answers ->", os.path.join(out, "answers.jsonl"))


if __name__ == "__main__":
    main()
