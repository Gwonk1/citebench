#!/bin/bash
# usage: nohup logs/queue_regrade_paid2.sh > logs/regrade_paid.log 2>&1 &
cd /home/graham/projects/citebench
while pgrep -f 'logs/queue_bar[e].sh|logs/queue_qwen[2].sh' >/dev/null; do sleep 20; done
echo "=== $(date '+%H:%M:%S') paid runs finished; regrading under g3"
for r in claude-fable-5-1:bare:v1 claude-opus-5-5:bare:v1 gpt-6-astra:bare:v1 gemini-3.1-pro-or:bare:v1 qwen3.8-max:bare:v2 deepseek-v4-pro:bare:v1 claude-sonnet-5-or:mcp:v1; do
  echo "=== $(date '+%H:%M:%S') regrade $r"; python3 grade.py --regrade --run-id $r --concurrency 3
done
python3 report.py && echo "=== REGRADE PAID DONE $(date)"
