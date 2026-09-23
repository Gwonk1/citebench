#!/bin/bash
# usage: nohup logs/queue_fixups.sh > logs/fixups.log 2>&1 &   (retry errored rows, top up Gemini, regrade, report)
cd /home/graham/projects/citebench
echo "=== $(date '+%H:%M:%S') deepseek retry errored rows"
python3 run.py --model deepseek-v4-pro --arm bare --limit 150 --confirm-spend --max-usd 0.6 --concurrency 4
echo "=== $(date '+%H:%M:%S') sonnet mcp retry errored rows"
python3 run.py --model claude-sonnet-5-or --arm mcp --limit 60 --confirm-spend --max-usd 1.5 --concurrency 2
echo "=== $(date '+%H:%M:%S') gemini top-up to 150"
python3 run.py --model gemini-3.1-pro-or --arm bare --limit 150 --confirm-spend --max-usd 2.2 --concurrency 4
for r in deepseek-v4-pro:bare:v1 claude-sonnet-5-or:mcp:v1 gemini-3.1-pro-or:bare:v1; do
  echo "=== $(date '+%H:%M:%S') regrade $r"; python3 grade.py --regrade --run-id $r --concurrency 3
done
python3 report.py && echo "=== FIXUPS DONE $(date)"
