#!/bin/bash
# usage: nohup logs/queue_resume_embed.sh > logs/resume_embed.log 2>&1 &   (restart the GA embed workers once Gemma's local MCP run has finished)
while pgrep -f 'logs/run_loca[l].sh' >/dev/null; do sleep 60; done
sudo -n systemctl start embed-corpus-ga embed-corpus-ga2 && echo "=== GA embed workers restarted $(date): $(systemctl is-active embed-corpus-ga embed-corpus-ga2 | paste -sd' ')"
