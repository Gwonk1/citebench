# Parse an analyze_citations text body into the fields the benchmark scores.
# FOUND means the reporter cite is a first page in the CourtListener index.
# It is not a statement that the case is still good law.
import re

WARNING_RE = re.compile(r'WARNING: Input case name "(.+?)" differs from verified "(.+?)"')
STATUTE_RE = re.compile(r'^Statutes:\n((?:.*\n?)*)', re.M)
CLUSTER_RE = re.compile(r"Cluster ID:\s+(\d+)")
AUTO_RE = re.compile(r"Auto-resolved from (\d+) clusters.*other cluster IDs:\s+([0-9, ]+)")
STATUS_RE = re.compile(r"Status:\s+(FOUND|NOT FOUND|AMBIGUOUS|INVALID|UNRESOLVABLE|PENDING)")


def parse(text):
    cases = []
    blocks = re.split(r"\n(?=  \d+\. )", text)
    for block in blocks:
        m = re.match(r"  (\d+)\. (.+)", block)
        if not m:
            continue
        sm = STATUS_RE.search(block)
        if not sm:
            continue
        wm = WARNING_RE.search(block)
        cm = CLUSTER_RE.search(block)
        am = AUTO_RE.search(block)
        cases.append({
            "n": int(m.group(1)),
            "cite": m.group(2).split(" — ")[0].strip(),
            "status": sm.group(1),
            "warning": bool(wm),
            "input_name": wm.group(1) if wm else None,
            "verified_name": wm.group(2) if wm else None,
            "cluster_id": int(cm.group(1)) if cm else None,
            "auto_resolved_from": int(am.group(1)) if am else None,
            "other_cluster_ids": (
                [int(x) for x in am.group(2).split(",") if x.strip()] if am else []
            ),
        })
    statutes = []
    sm = STATUTE_RE.search(text)
    if sm:
        for line in sm.group(1).splitlines():
            qm = re.search(r'"(.+?)"', line)
            if qm:
                statutes.append(qm.group(1))
    header_warn = "possible hallucinations" in text
    return {"cases": cases, "statutes": statutes, "header_warning": header_warn}
