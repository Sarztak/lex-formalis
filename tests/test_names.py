"""
Test deterministic name generation on construct-candidate nodes.
Construct candidates: container_intro, container_bare, scope_rule, scope_def.
Writes log to logs/names_<timestamp>.txt
"""

import json
import sys
from datetime import UTC, datetime

from formalize import node_to_name

CLASSIFY_LOG = "logs/classify_rules_20260730_215825.json"
CONSTRUCT_TAGS = {"scope_rule", "scope_def", "container_intro", "container_bare"}


def main():
    with open(CLASSIFY_LOG) as f:
        data = json.load(f)

    results = []
    for entry in data["results"]:
        tags = {t["construct"] for t in entry.get("tags", [])}
        hit = tags & CONSTRUCT_TAGS
        if hit:
            nid = entry["id"]
            name = node_to_name(
                nid,
                entry.get("header", ""),
                entry.get("chapeau", ""),
                entry.get("body", ""),
            )
            results.append((nid, sorted(hit), name))

    lines = [
        f"Construct-candidate nodes: {len(results)}",
        "",
        f"{'ID':<22} {'TAGS':<50} NAME",
        "-" * 110,
    ]
    for nid, tags, name in results:
        lines.append(f"{nid:<22} {tags!s:<50} {name}")

    out = "\n".join(lines)
    print(out)

    ts = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    fname = f"logs/names_{ts}.txt"
    with open(fname, "w") as f:
        f.write(out + "\n")
    print(f"\nWritten to {fname}", file=sys.stderr)


if __name__ == "__main__":
    main()
