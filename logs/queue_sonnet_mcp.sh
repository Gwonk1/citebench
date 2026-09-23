#!/bin/bash
# usage: nohup logs/queue_sonnet_mcp.sh > logs/sonnet_mcp.log 2>&1 &
cd /home/graham/projects/citebench
python3 run.py --model claude-sonnet-5-or --arm mcp --limit 60 --confirm-spend --max-usd 4.8 --concurrency 2
echo "=== SONNET MCP DONE $(date)"
