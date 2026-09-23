#!/bin/bash
# usage: nohup logs/queue_final_regrade.sh > logs/final_regrade.log 2>&1 &   (after ALL queues: full regrade under g4, final report)
cd /home/graham/projects/citebench
while pgrep -f 'logs/queue_local_regrad[e].sh|logs/queue_flas[h].sh|logs/queue_flash[2].sh|logs/queue_fixup[s].sh|logs/run_loca[l].sh' >/dev/null; do sleep 120; done
echo "=== $(date '+%H:%M:%S') all queues finished; FULL regrade under $(grep -o 'g4[^"]*' grade.py | head -1)"
python3 grade.py --regrade --concurrency 3 && python3 report.py && echo "=== FINAL REGRADE DONE $(date)"
