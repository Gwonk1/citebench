#!/bin/bash
# usage: nohup logs/queue_grade2.sh > logs/grade2.log 2>&1 &
cd /home/graham/projects/citebench
python3 grade.py --run-id claude-opus-5-5:bare:v1 --concurrency 3
python3 grade.py --run-id gpt-6-astra:bare:v1 --concurrency 3
echo "=== GRADE2 DONE $(date)"
