#!/bin/bash
# usage: nohup logs/queue_audit_rebuild.sh > logs/audit_rebuild.log 2>&1 &   (after the final g5 regrade: rebuild the frozen 60-card audit packet with correct attribution and republish the isyfert review page)
cd /home/graham/projects/citebench
while pgrep -f 'logs/queue_final_regrad[e].sh' >/dev/null; do sleep 120; done
grep -q 'FINAL REGRADE DONE' logs/final_regrade.log || { echo "final regrade did not finish cleanly; not rebuilding"; exit 1; }
echo "=== $(date '+%H:%M:%S') regrade done; rebuilding frozen packet"
cp audit/packet.json audit/packet.json.bak.pre-g5-20260922; cp audit/index.html audit/index.html.bak.pre-g5-20260922
PYTHONDONTWRITEBYTECODE=1 python3 audit/build_packet.py --frozen audit/packet.json.bak.pre-g5-20260922 --out audit/packet.json || exit 1
python3 audit/build_page.py --packet audit/packet.json --out audit/index.html || exit 1
scp -q audit/index.html cloud-ts:/var/www/html/namedhosts/www.isyfert.com/enrich/citebench-audit/index.html && ssh cloud-ts 'cd /var/www/html/namedhosts/www.isyfert.com/enrich/citebench-audit && php -l index.html' && echo "=== AUDIT PAGE REPUBLISHED $(date)"
