"""
For each base-case "In general"/"General rule" node, call node_text on its parent
to get the full flattened context, then ask Claude to identify exception pairs:
which node overrides/qualifies which other node.

Output: logs/exceptions/{section}_exception_pairs.json

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

sys.path.insert(0, os.path.dirname(__file__))
from statute import load_lookup, build_child_map, node_text  # type: ignore

LOG_DIR = "logs/exceptions"
MODEL = "claude-sonnet-4-6"

EXC_PATTERN = re.compile(
    r"\bexception|limitation|special rule|notwithstanding|shall not\b|except as\b", re.I
)

SYSTEM = (
    "You are an expert tax attorney with deep knowledge of the Internal Revenue Code (IRC). "
    "You reason carefully about statutory structure and interpret provisions with precision."
)

TASK = (
    "Below is the text of an IRC provision. It contains a general rule and one or more siblings. "
    "Identify every pair where one node overrides, qualifies, limits, or carves out from another node. "
    "For each pair, the first node_id is the overriding node (the exception), "
    "the second node_id is the overridden node (the one being excepted). "
    "Only include direct overrides — not downstream effects. "
    "Node ids appear in the text as the identifier before the colon or at the start of each provision. "
    "Also identify exceptions to exceptions: if node B overrides node A, and node C overrides node B, "
    "report both pairs. "
    "Return a JSON array only:\n"
    '[{"overriding": "node_id", "overridden": "node_id", "reason": "one line"}]'
)


def is_base_case(node, node_map, parent_map):
    own_text = " ".join(node.get(f, "") for f in ("chapeau", "body", "continuation"))
    if EXC_PATTERN.search(own_text):
        return False
    nid = parent_map.get(node["id"], {}).get("id") if parent_map.get(node["id"]) else None
    while nid and nid in node_map:
        h = node_map[nid].get("header", "").strip()
        if EXC_PATTERN.search(h):
            return False
        nid = parent_map.get(nid, {}).get("id") if parent_map.get(nid) else None
    return True


def build_node_maps(tree):
    node_map, parent_map = {}, {}
    def walk(node):
        node_map[node["id"]] = node
        for child in node.get("children", []):
            parent_map[child["id"]] = node
            walk(child)
    walk(tree)
    return node_map, parent_map


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

    with open(f"data/{args.section}_tree.json", encoding="utf-8") as f:
        tree = json.load(f)

    raw_node_map, raw_parent_map = build_node_maps(tree)

    lookup = load_lookup(args.section)
    child_map = build_child_map(lookup)

    # find base-case In general / General rule nodes, deduplicate by parent_id
    # if two base-case nodes share the same parent, calling node_text on the parent
    # would produce identical context — keep only the first occurrence per parent
    seen_parents = set()
    parent_ids = {}  # parent_id -> base_case node_id
    for node in sorted(raw_node_map.values(), key=lambda n: n["id"]):
        if node.get("header", "").strip().lower() not in ("in general", "general rule"):
            continue
        if not is_base_case(node, raw_node_map, raw_parent_map):
            continue
        parent = raw_parent_map.get(node["id"])
        if not parent:
            continue
        pid = parent["id"]
        if pid in seen_parents:
            continue
        seen_parents.add(pid)
        parent_ids[pid] = node["id"]

    print(f"{len(parent_ids)} unique parents to evaluate", file=sys.stderr)

    tasks = []
    for pid in parent_ids:
        if pid not in lookup:
            # try via child_map
            if pid not in child_map:
                print(f"  [skip] {pid} not in lookup", file=sys.stderr)
                continue
        try:
            _, text = node_text(pid, lookup, child_map)
            tasks.append((pid, text))
        except KeyError as e:
            print(f"  [skip] {pid}: {e}", file=sys.stderr)

    all_pairs = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_map = {executor.submit(run_llm, pid, text): pid for pid, text in tasks}
        for future in concurrent.futures.as_completed(future_map):
            pid = future_map[future]
            pairs, error = future.result()
            if error:
                print(f"  [error] {pid}: {error}", file=sys.stderr)
            else:
                print(f"  [ok] {pid}: {len(pairs)} pairs", file=sys.stderr)
                for p in pairs:
                    p["context_parent"] = pid
                all_pairs.extend(pairs)

    all_pairs.sort(key=lambda p: (p.get("context_parent", ""), p.get("overriding", "")))

    os.makedirs(LOG_DIR, exist_ok=True)
    out_path = os.path.join(LOG_DIR, f"{args.section}_exception_pairs.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_pairs, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path} — {len(all_pairs)} pairs total", file=sys.stderr)

    for p in all_pairs:
        print(f"  {p['overriding']} → {p['overridden']}  | {p['reason']}")


if __name__ == "__main__":
    main()
