# usage: python3 run.py items/pilot.jsonl [--out results/YYYYMMDD] [--ids p01,p02]
# One analyze_citations call per item. Sleeps between calls. Skips ids already on disk.
import argparse
import json
import os
import time

import clmcp

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("items")
    ap.add_argument("--out", default=None)
    ap.add_argument("--ids", default="")
    ap.add_argument("--sleep", type=float, default=1.5)
    args = ap.parse_args()
    want = set(x for x in args.ids.split(",") if x)
    out = args.out or os.path.join(HERE, "results", time.strftime("%Y%m%d"))
    os.makedirs(out, exist_ok=True)
    health = clmcp.health()
    open(os.path.join(out, "health.json"), "w").write(json.dumps(health, indent=2) + "\n")
    print("server", health.get("version"), health.get("status"))
    rows = []
    with open(args.items) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    for i, row in enumerate(rows):
        if want and row["id"] not in want:
            continue
        dest = os.path.join(out, row["id"] + ".txt")
        if os.path.exists(dest):
            print("skip", row["id"])
            continue
        if i and not os.path.exists(dest):
            time.sleep(args.sleep)
        try:
            body = fetch(row)
        except Exception as e:
            body = "ERROR " + str(e)[:500]
        open(dest, "w").write(body)
        if not body.endswith("\n"):
            open(dest, "a").write("\n")
        print("wrote", row["id"], "chars", len(body))


def fetch(row):
    tool = row.get("tool") or "analyze_citations"
    if tool == "analyze_citations":
        return clmcp.analyze(row["text"])
    if tool == "cluster":
        return clmcp.get_item(
            "clusters",
            row["cluster_id"],
            ["id", "case_name", "date_filed", "citations", "precedential_status", "citation_count"],
        )
    if tool == "opinion":
        body = clmcp.get_item("opinions", row["opinion_id"], ["id", "cluster", "type", "plain_text", "html"])
        snippet = row.get("snippet") or ""
        found = snippet and snippet in body
        head = body[:1200]
        return f"snippet_found={found}\n---\n{head}\n"
    if tool == "court":
        return clmcp.get_item(
            "courts",
            row["court_id"],
            ["id", "citation_string", "short_name", "full_name"],
        )
    if tool == "fldca":
        import re
        cluster = clmcp.get_item(
            "clusters", row["cluster_id"],
            ["id", "case_name", "docket", "citations"],
        )
        time.sleep(1.0)
        m = re.search(r"/dockets/(\d+)/", cluster)
        docket = ""
        if m:
            docket = clmcp.get_item(
                "dockets", int(m.group(1)),
                ["id", "court", "docket_number", "case_name"],
            )
        return cluster + "\n--- docket ---\n" + docket


if __name__ == "__main__":
    main()
