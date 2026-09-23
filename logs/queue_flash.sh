#!/bin/bash
# usage: nohup logs/queue_flash.sh > logs/flash.log 2>&1 &   (flash-tier models, bare + mcp arms, after fixups finish)
cd /home/graham/projects/citebench
while pgrep -f 'logs/queue_fixup[s].sh' >/dev/null; do sleep 30; done
echo "=== $(date '+%H:%M:%S') fixups finished; flash tier"
for spec in "qwen3.8-flash-or bare 60 0.4" "deepseek-v4.1-flash-or bare 60 0.4" "gemini-3.8-flash-or bare 40 0.6" \
            "qwen3.8-flash-or mcp 60 1.0" "deepseek-v4.1-flash-or mcp 60 1.0" "gemini-3.8-flash-or mcp 40 2.5"; do
  set -- $spec
  echo "=== $(date '+%H:%M:%S') START $1 $2 (limit $3, cap \$$4)"
  python3 run.py --model $1 --arm $2 --limit $3 --confirm-spend --max-usd $4 --concurrency 3
done
for r in qwen3.8-flash-or:bare:v1 deepseek-v4.1-flash-or:bare:v1 gemini-3.8-flash-or:bare:v1 qwen3.8-flash-or:mcp:v1 deepseek-v4.1-flash-or:mcp:v1 gemini-3.8-flash-or:mcp:v1; do
  echo "=== $(date '+%H:%M:%S') grade $r"; python3 grade.py --run-id $r --concurrency 3
done
python3 report.py && echo "=== FLASH DONE $(date)"
