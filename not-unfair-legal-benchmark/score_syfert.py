# usage: python3 score_syfert.py results/20261026-syfert-raw [--tasks items/tasks.jsonl]
# Grades <dir>/answers.jsonl (written by run_syfert.py) with grade.grade_item: class table, controls row,
# total, no_answer_line count, and every miss with the grader's reason. Writes <dir>/score.txt.
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grade_answers  # noqa: E402

VERSION = open(os.path.join(HERE, "VERSION")).read().strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--tasks", default=os.path.join(HERE, "items", "tasks.jsonl"))
    args = ap.parse_args()
    tasks = [json.loads(l) for l in open(args.tasks) if l.strip()]
    answers = grade_answers.load_answers([os.path.join(args.dir, "answers.jsonl")])
    server = {}
    sp = os.path.join(args.dir, "server.json")
    if os.path.exists(sp):
        server = (json.load(open(sp)).get("serverInfo") or {})
    by_class, passed, no_line, misses, unscored = grade_answers.score(tasks, answers)
    title = (f"raw Syfert MCP tool arm, grader v{VERSION}, server {server.get('name', '?')} {server.get('version', '?')}, "
             f"{len(answers)} answers in {args.dir}")
    text = grade_answers.table(by_class, passed, no_line, unscored, title=title)
    text += "\n\n" + "\n".join(f"miss {iid:16} {klass:12} {why}" for iid, klass, why in misses)
    print(text)
    with open(os.path.join(args.dir, "score.txt"), "w") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
