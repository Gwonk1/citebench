# Grade a file of saved answers with grade.py and print the score table.
# usage: python3 grade_answers.py answers.jsonl [more.jsonl ...] [--tasks items/tasks.jsonl] [--misses]
#
# Each line of an answers file is {"id": "<task id>", "answer": "<the text the arm sent back>"}.
# The last line for an id wins. Controls (kind: control) are shown on their own
# row and in the total, so a false-positive rate can be read off the table.
# no_answer_line counts answers that had no "ANSWER:" line (graded on the last
# non-empty line instead).
import argparse
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grade  # noqa: E402


def load_answers(paths):
    answers = {}
    for path in paths:
        if os.path.isdir(path):
            files = sorted(os.path.join(path, f) for f in os.listdir(path) if f.endswith(".jsonl"))
        else:
            files = [path]
        for fn in files:
            for line in open(fn):
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if "answer" not in row:
                    continue  # a task shard or other file that is not an answers file
                answers[row["id"]] = row.get("answer") or ""
    return answers


def score(tasks, answers):
    by_class = Counter()
    passed = Counter()
    no_line = 0
    misses = []
    unscored = []
    for t in tasks:
        klass = t["class"]
        a = answers.get(t["id"])
        if a is None:
            unscored.append(t["id"])
            continue
        by_class[klass] += 1
        r = grade.grade_item(a, t["gold"])
        if r["no_answer_line"]:
            no_line += 1
        if r["passed"]:
            passed[klass] += 1
        else:
            misses.append((t["id"], klass, r["reason"]))
    return by_class, passed, no_line, misses, unscored


def table(by_class, passed, no_line, unscored, title=""):
    lines = []
    if title:
        lines.append(title)
    lines.append(f"{'class':12} {'pass':>5} {'miss':>5} {'n':>5}")
    tot_p = tot_n = 0
    for klass in sorted(by_class):
        n = by_class[klass]
        if klass in ("control",):
            continue
        p = passed[klass]
        lines.append(f"{klass:12} {p:5} {n - p:5} {n:5}")
        tot_p += p
        tot_n += n
    lines.append(f"{'traps':12} {tot_p:5} {tot_n - tot_p:5} {tot_n:5}")
    if by_class.get("control"):
        n = by_class["control"]
        p = passed["control"]
        lines.append(f"{'control':12} {p:5} {n - p:5} {n:5}   (false positives: {n - p})")
        tot_p += p
        tot_n += n
    lines.append(f"{'total':12} {tot_p:5} {tot_n - tot_p:5} {tot_n:5}")
    lines.append(f"no ANSWER line: {no_line}; no saved answer (not counted above): {len(unscored)}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("answers", nargs="+")
    ap.add_argument("--tasks", default=os.path.join(HERE, "items", "tasks.jsonl"))
    ap.add_argument("--misses", action="store_true", help="list every miss with the grader's reason")
    args = ap.parse_args()
    tasks = [json.loads(l) for l in open(args.tasks) if l.strip()]
    answers = load_answers(args.answers)
    by_class, passed, no_line, misses, unscored = score(tasks, answers)
    print(table(by_class, passed, no_line, unscored))
    if args.misses:
        print()
        for iid, klass, why in misses:
            print(f"miss {iid:16} {klass:12} {why}")


if __name__ == "__main__":
    main()
