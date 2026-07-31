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
Read the following provision of US tax law and determine its logical structure.

{provision_text}

Answer the following questions in order and stop at the first that applies:

1. Do the sub-provisions conditionally define or modify the concept in the main provision — that is, does the meaning or application of the provision change depending on a condition, context, or reference? Or would this provision be incomplete without a computation — does it require specifying inputs, a condition, and an output to be meaningful? If either applies: "scope". Also identify what the inputs, condition, and output are.
2. Does this provision only make complete sense when all sub-provisions are simultaneously satisfied? If yes: "structure".
3. Do the sub-provisions represent mutually exclusive and exhaustive alternatives of a single named concept stated in the provision? To verify: identify what that named concept (the object being enumerated) is. If no such named concept exists in the provision text, it is not an enumeration. If yes: "enumeration".
4. If none of the above: "other".

Respond with JSON only, no prose, no markdown fences:
{{"construct": "enumeration"|"scope"|"structure"|"other", "reason": "one sentence", "inputs": null, "condition": null, "output": null}}
(set inputs/condition/output only when construct is "scope", otherwise null)
"""


def walk(node):
    yield node
    for c in node.get("children", []):
        yield from walk(c)


def provision_text(node):
    parts = []
    if node.get("header"):
        parts.append(node["header"])
    if node.get("chapeau"):
        parts.append(node["chapeau"])
    if node.get("body"):
        parts.append(node["body"])
    return " ".join(parts).strip()


def format_provision(node, children):
    text = provision_text(node)
    lines = [text] if text else []
    for c in children:
        sub = provision_text(c)
        if sub:
            lines.append(f"  - {sub}")
    return "\n".join(lines) or "(no text)"


def call_agent(node_id, header, chapeau, body, children):
    node = {"header": header, "chapeau": chapeau, "body": body}
    prompt = PROMPT_TMPL.format(provision_text=format_provision(node, children))
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", "claude-sonnet-5"],
        capture_output=True, text=True, timeout=60, check=False,
    )
    raw = result.stdout.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()
    # find first { in case model prefixes prose before JSON
    brace = raw.find("{")
    if brace > 0:
        raw = raw[brace:]
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
