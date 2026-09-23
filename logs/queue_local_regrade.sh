#!/bin/bash
# usage: nohup logs/queue_local_regrade.sh > logs/local_regrade.log 2>&1 &   (after Gemma finishes both arms: regrade local runs, final report)
cd /home/graham/projects/citebench
while pgrep -f 'logs/run_loca[l].sh' >/dev/null; do sleep 60; done
while pgrep -f 'logs/queue_flas[h].sh' >/dev/null; do sleep 60; done
echo "=== $(date '+%H:%M:%S') local runs + flash finished; regrading local under g3"
python3 grade.py --regrade --run-id local-gemma:bare:v1 --concurrency 3
python3 grade.py --regrade --run-id local-gemma:mcp:v1 --concurrency 3
python3 report.py && echo "=== LOCAL REGRADE DONE $(date)"
