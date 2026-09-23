#!/bin/bash
# usage: nohup logs/queue_flash2.sh > logs/flash2.log 2>&1 &   (after flash tier: clean rerun of qwen flash bare under the reasoning cap, drop probe rows, grade, report)
cd /home/graham/projects/citebench
while pgrep -f 'logs/queue_flas[h].sh' >/dev/null; do sleep 30; done
echo "=== $(date '+%H:%M:%S') flash tier finished; qwen flash bare clean rerun"
sqlite3 results/results.db "delete from grades where run_id='qwen3.8-flash-or:bare:v1'; delete from answers where run_id='qwen3.8-flash-or:bare:v1'; delete from runs where run_id='qwen3.8-flash-or:bare:v1'; delete from grades where run_id like '%:probe'; delete from answers where run_id like '%:probe'; delete from runs where run_id like '%:probe';"
python3 run.py --model qwen3.8-flash-or --arm bare --limit 60 --confirm-spend --max-usd 0.4 --concurrency 3
python3 grade.py --run-id qwen3.8-flash-or:bare:v1 --concurrency 3
python3 report.py && echo "=== FLASH2 DONE $(date)"
