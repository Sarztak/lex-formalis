"""
Pre-classify ambiguous nodes before formalization.
Asks agent: enumeration | structure | scope | none.
Run with --limit N to test on N nodes (default 5).
Writes logs/pre_classify_<timestamp>.json
"""

import argparse
import json
import random
import subprocess
import sys
from datetime import UTC, datetime

CLASSIFY_LOG = "logs/classify_rules_20260730_215825.json"
TREE_FILE = "7701_tree.json"

# tag combos deterministic enough to skip agent classification
SKIP_COMBOS = {
    frozenset(["leaf"]),
    frozenset(["definition", "leaf"]),
    frozenset(["exception", "leaf"]),
    frozenset(["definition", "exception", "leaf"]),
    frozenset(["container_bare", "scope_rule"]),
    frozenset(["container_intro", "scope_def", "scope_rule"]),
    frozenset(["container_bare", "exception", "scope_rule"]),
}

PROMPT_TMPL = """\
You are classifying a provision of US tax law for formalization in Catala.

Given the provision below, decide which Catala construct best represents it:

- enumeration : children are mutually exclusive, exhaustive alternatives of one concept
- structure   : children are named fields / conjunctive criteria of one concept
- scope       : a computational rule with inputs, conditions, and an output; also applies when the same term is defined differently depending on a condition (same output variable, multiple conditional definitions)
- none        : this node is a grouping wrapper; no standalone construct needed

Respond with JSON only, no prose, no markdown fences:
{{"construct": "enumeration"|"structure"|"scope"|"none", "reason": "one sentence"}}

Provision:
id: {node_id}
header: {header}
chapeau: {chapeau}
body: {body}

Children:
{children}
"""


def walk(node):
    yield node
    for c in node.get("children", []):
        yield from walk(c)


def child_summary(children):
    lines = []
    for c in children:
        parts = [f"[{c['id']}]"]
        if c.get("header"):
            parts.append(f"header: {c['header']}")
        if c.get("chapeau"):
            parts.append(f"chapeau: {c['chapeau']}")
        if c.get("body"):
            parts.append(f"body: {c['body']}")
        lines.append("  - " + " | ".join(parts))
    return "\n".join(lines) or "  (none)"


def call_agent(node_id, header, chapeau, body, children):
    prompt = PROMPT_TMPL.format(
        node_id=node_id,
        header=header or "(none)",
        chapeau=chapeau or "(none)",
        body=body or "(none)",
        children=child_summary(children),
    )
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", "claude-haiku-4-5-20251001"],
        capture_output=True, text=True, timeout=60, check=False,
    )
    raw = result.stdout.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()
    try:
        parsed, _ = json.JSONDecoder().raw_decode(raw)
        return parsed, None
    except json.JSONDecodeError:
        return None, raw[:300]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--nodes", nargs="+", default=None, help="run only these node IDs")
    args = parser.parse_args()

    with open(CLASSIFY_LOG) as f:
        classify_data = json.load(f)

    with open(TREE_FILE) as f:
        tree_data = json.load(f)

    node_map = {n["id"]: n for n in walk(tree_data)}

    # collect ambiguous nodes
    candidates = []
    for entry in classify_data["results"]:
        tags = frozenset(t["construct"] for t in entry.get("tags", []))
        if tags in SKIP_COMBOS:
            continue
        if not tags:
            continue
        candidates.append((entry["id"], tags))

    if args.nodes:
        subset = [(nid, tags) for nid, tags in candidates if nid in args.nodes]
    else:
        random.shuffle(candidates)
        subset = candidates if args.limit is None else candidates[: args.limit]
    print(f"Ambiguous nodes total: {len(candidates)}, running: {len(subset)}", file=sys.stderr)

    results = []
    for node_id, tags in subset:
        node = node_map.get(node_id, {})
        parsed, error = call_agent(
            node_id,
            node.get("header", ""),
            node.get("chapeau", ""),
            node.get("body", ""),
            node.get("children", []),
        )
        row = {
            "id": node_id,
            "tags": sorted(tags),
            "header": node.get("header", ""),
            "result": parsed,
            "error": error,
        }
        results.append(row)
        construct = parsed.get("construct", "ERROR") if parsed else "ERROR"
        reason = parsed.get("reason", error or "")[:80] if parsed else (error or "")[:80]
        print(f"  {node_id:25s} tags={sorted(tags)} → {construct}")
        print(f"    {reason}")

    ts = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    out_path = f"logs/pre_classify_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nWritten: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
