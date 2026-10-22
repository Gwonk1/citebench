# Grade saved answers with grade.py. The CourtListener bodies are one arm.
# usage: python3 score_saved.py [results-dir]
import json
import os
import sys
from collections import Counter

import grade

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS = os.path.join(HERE, "items", "tasks.jsonl")
RESULTS = os.path.join(HERE, "results")


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
    unscored = []
    lines = []
    for row in rows:
        paths = find_result(row["id"])
        by_class[row["class"]] += 1
        if not paths:
            unscored.append(row["id"])
            continue
        answer = open(paths[-1]).read()
        ok, why = grade.grade(answer, row["gold"])
        if ok:
            passed[row["class"]] += 1
        else:
            missed[row["class"]] += 1
            lines.append(f"miss {row['id']:16} {row['class']:12} {why}")
    print()
    print(f"{'class':16} {'pass':>5} {'miss':>5} {'no answer':>10}")
    for klass in sorted(by_class):
        p = passed[klass]
        m = missed[klass]
        print(f"{klass:16} {p:5} {m:5}")
    print(f"{'total':16} {sum(passed.values()):5} {sum(missed.values()):5} {len(unscored):10}")
    if unscored:
        print("no saved answer:", ", ".join(unscored))
    print()
    print("\n".join(lines))
    out = os.path.join(RESULTS, "courtlistener-arm.txt")
    with open(out, "w") as f:
        f.write("CourtListener arm, graded as answer text against items/tasks.jsonl\n")
        f.write(f"pass {sum(passed.values())}  miss {sum(missed.values())}  no saved answer {len(unscored)}\n\n")
        for klass in sorted(by_class):
            f.write(f"{klass:16} pass {passed[klass]:3}  miss {missed[klass]:3}\n")
        if unscored:
            f.write("\nno saved answer: " + ", ".join(unscored) + "\n")
        f.write("\n" + "\n".join(lines) + "\n")
    print("\nwrote", out)


if __name__ == "__main__":
    main()
