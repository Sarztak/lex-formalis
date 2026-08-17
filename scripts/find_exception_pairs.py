"""
For each base-case "In general"/"General rule" node in the merged lookup,
call node_text on its parent to get the full flattened context, then ask
Claude to identify exception pairs: which node overrides/qualifies which.

Uses the merged lookup (logs/flatten/merged_{section}.json) throughout —
not the raw tree. Same approach as exception_context.py.

Output: logs/exceptions/{section}_exception_pairs_{timestamp}.json

Usage:
    python scripts/find_exception_pairs.py 7701
"""

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from statute import load_lookup, build_child_map, node_text, get_parent  # type: ignore

LOG_DIR = "logs/exceptions"
MODEL = "claude-sonnet-4-6"

EXC_PATTERN = re.compile(
    r"\bexception|limitation|special rule|notwithstanding|shall not\b|except as\b", re.I
)
DEFN_PATTERN = re.compile(r'the terms?\s+[““‘]|any term used\b', re.I)

SYSTEM = (
    "You are an expert tax attorney with deep knowledge of the Internal Revenue Code (IRC). "
    "You reason carefully about statutory structure and interpret provisions with precision."
)

TASK = (
    "Below is the text of an IRC provision. It contains a general rule and one or more siblings. "
    "Identify every pair(if exists) where one node overrides, qualifies, limits, or carves out from another node. "
    "For each pair, the first node_id is the overriding node (the exception), "
    "the second node_id is the overridden node (the one being excepted). "
    "Only include direct overrides — not downstream effects. "
    "Node ids appear in the text as the identifier before the colon or at the start of each provision. "
    "Also identify exceptions to exceptions: if node B overrides node A, and node C overrides node B, "
    "report both pairs. "
    "For each pair provide structured reasoning across three dimensions:\n"
    "  mechanism: how the exception acts — one of: carves_out, displaces, limits, re_imposes, bars, extends, other\n"
    "  trigger: array of what activates the exception — each one of: taxpayer_condition, temporal, regulatory_action, other\n"
    "  scope: what is changed in DAG terms — one of: input, output\n"
    "Return a JSON array only:\n"
    '[{"overriding": "node_id", "overridden": "node_id", "mechanism": "...", "trigger": [...], "scope": "...", "reason": "one line"}]'
)


def is_base_case(node, lookup):
    """Node must have In general/General rule header, no exception language in own text, no definition language, and no exception keyword in any ancestor header."""
    own_text = " ".join(node.get(f, "") for f in ("chapeau", "body", "merged_body", "continuation"))
    if DEFN_PATTERN.search(own_text) or EXC_PATTERN.search(own_text):
        return False
    nid = node["id"]
    while True:
        try:
            parent = get_parent(nid, lookup)
        except KeyError:
            break
        if EXC_PATTERN.search(parent.get("header", "")):
            return False
        nid = parent["id"]
    return True


def run_llm(parent_id, text):
    prompt = "\n\n".join([SYSTEM, TASK, f"Node id: {parent_id}\n\n{text}"])
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", MODEL],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None, result.stderr[:300]
    raw = result.stdout.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0].strip()
    start, end = raw.find("["), raw.rfind("]")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    try:
        return json.loads(raw), None
    except json.JSONDecodeError:
        return None, f"parse error: {raw[:200]}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("section", default="7701", nargs="?")
    args = parser.parse_args()

    lookup = load_lookup(args.section)
    child_map = build_child_map(lookup)

    # find base-case In general / General rule nodes from merged lookup
    # deduplicate by parent_id — same parent would produce identical context
    seen_parents = set()
    tasks = []

    for node in sorted(lookup.values(), key=lambda n: n["id"]):
        if node.get("header", "").strip().lower() not in ("in general", "general rule"):
            continue
        if not is_base_case(node, lookup):
            continue
        try:
            parent = get_parent(node["id"], lookup)
        except KeyError:
            print(f"  [skip] {node['id']}: no parent in lookup", file=sys.stderr)
            continue
        pid = parent["id"]
        if pid in seen_parents:
            continue
        seen_parents.add(pid)
        try:
            _, text = node_text(pid, lookup, child_map)
            tasks.append((pid, text))
        except KeyError as e:
            print(f"  [skip] {pid}: {e}", file=sys.stderr)

    print(f"{len(tasks)} unique parents to evaluate", file=sys.stderr)

    all_pairs = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_map = {executor.submit(run_llm, pid, text): pid for pid, text in tasks}
        for future in concurrent.futures.as_completed(future_map):
            pid = future_map[future]
            pairs, error = future.result()
            if error:
                print(f"  [error] {pid}: {error}", file=sys.stderr)
            else:
                pairs = pairs or []
                print(f"  [ok] {pid}: {len(pairs)} pairs", file=sys.stderr)
                for p in pairs:
                    p["context_parent"] = pid
                all_pairs.extend(pairs)

    all_pairs.sort(key=lambda p: (p.get("context_parent", ""), p.get("overriding", "")))

    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(LOG_DIR, f"{args.section}_exception_pairs_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_pairs, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path} — {len(all_pairs)} pairs total", file=sys.stderr)

    for p in all_pairs:
        print(f"  {p['overriding']} → {p['overridden']}  | {p['reason']}")


if __name__ == "__main__":
    main()
