#!/bin/bash
# usage: nohup logs/run_paid_bare.sh > logs/paid_bare.log 2>&1 &
cd /home/graham/projects/citebench
for spec in "claude-fable-5-1 14.5" "claude-opus-5-5 5.5" "gpt-6-astra 14.5" "gemini-3.1-pro-or 3.6" "kimi-k3 4.2" "qwen3.8-max 1.9" "deepseek-v4-pro 0.8"; do
  set -- $spec
  echo "=== $(date '+%H:%M:%S') START $1 (cap \$$2, limit 150)"
  python3 run.py --model $1 --arm bare --limit 150 --confirm-spend --max-usd $2 --concurrency 4
  echo "=== $(date '+%H:%M:%S') END $1 rc=$?"
done
echo "=== ALL BARE DONE $(date)"
