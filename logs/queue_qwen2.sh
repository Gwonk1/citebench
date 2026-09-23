#!/bin/bash
# usage: nohup logs/queue_qwen2.sh > logs/qwen2.log 2>&1 &
cd /home/graham/projects/citebench
python3 run.py --model qwen3.8-max --arm bare --limit 150 --tag v2 --confirm-spend --max-usd 1.9 --concurrency 4
echo "=== QWEN2 DONE $(date)"
