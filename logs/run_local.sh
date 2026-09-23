#!/bin/bash
# usage: nohup logs/run_local.sh > logs/local.log 2>&1 &
cd /home/graham/projects/citebench
python3 run.py --model local-gemma --arm bare --concurrency 2
python3 run.py --model local-gemma --arm mcp --concurrency 2
echo "=== LOCAL DONE $(date)"
