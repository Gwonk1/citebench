# Grade saved answers with grade.py. The CourtListener bodies are one arm.
# usage: python3 score_saved.py [results-dir]
#
# The saved bodies are raw tool output, not model answers: none has an ANSWER:
# line, so each is graded on its last non-empty line (no_answer_line is counted).
import json
import os
import sys
from collections import Counter

import grade

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS = os.path.join(HERE, "items", "tasks.jsonl")
RESULTS = os.path.join(HERE, "results")
VERSION = open(os.path.join(HERE, "VERSION")).read().strip()


def find_result(iid):
    found = []
    for dirpath, _, files in os.walk(RESULTS):
        if iid + ".txt" in files:
            found.append(os.path.join(dirpath, iid + ".txt"))
    return sorted(found)


def main():
    rows = [json.loads(line) for line in open(TASKS) if line.strip()]
    bad = []
    for row in rows:
        ok, why = grade.self_check(row)
        if not ok:
            bad.append(row["id"] + ": " + why)
    if bad:
        print("self-check failed")
        print("\n".join(bad))
        sys.exit(1)
    print(f"self-check {len(rows)} tasks")

    by_class = Counter()
    passed = Counter()
    missed = Counter()
    no_line = 0
    unscored = []
    lines = []
    for row in rows:
        paths = find_result(row["id"])
        by_class[row["class"]] += 1
        if not paths:
            unscored.append(row["id"])
            continue
        answer = open(paths[-1]).read()
        r = grade.grade_item(answer, row["gold"])
        if r["no_answer_line"]:
            no_line += 1
        if r["passed"]:
            passed[row["class"]] += 1
        else:
            missed[row["class"]] += 1
            lines.append(f"miss {row['id']:16} {row['class']:12} {r['reason']}")
    print()
    print(f"{'class':16} {'pass':>5} {'miss':>5}")
    for klass in sorted(by_class):
        print(f"{klass:16} {passed[klass]:5} {missed[klass]:5}")
    print(f"{'total':16} {sum(passed.values()):5} {sum(missed.values()):5}   no saved answer {len(unscored)}   no ANSWER line {no_line}")
    if unscored:
        print("no saved answer:", ", ".join(unscored))
    print()
    print("\n".join(lines))
    out = os.path.join(RESULTS, "courtlistener-arm.txt")
    with open(out, "w") as f:
        f.write(f"CourtListener arm (raw analyze_citations bodies, server 9386476), graded as answer text against items/tasks.jsonl v{VERSION}\n")
        f.write("The saved bodies have no ANSWER: line; each is graded on its last non-empty line.\n")
        f.write(f"pass {sum(passed.values())}  miss {sum(missed.values())}  no saved answer {len(unscored)}  no ANSWER line {no_line}\n\n")
        for klass in sorted(by_class):
            f.write(f"{klass:16} pass {passed[klass]:3}  miss {missed[klass]:3}\n")
        if unscored:
            f.write("\nno saved answer (added in v1.1, never sent to CourtListener): " + ", ".join(unscored) + "\n")
        f.write("\n" + "\n".join(lines) + "\n")
    print("\nwrote", out)


if __name__ == "__main__":
    main()
