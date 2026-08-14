import argparse
import json
import os
import re
import sys


def load_lookup(section):
    path = f"logs/flatten/merged_{section}.json"
    if not os.path.exists(path):
        sys.exit(f"Missing: {path} — run scripts/show_flatten.py {section} first")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return {n["id"]: n for n in d["nodes"]}


def node_text(node_id, lookup):
    """Return full text of a node, walking down to L0 children.
    If the id is not found, strips one level at a time until found or exhausted."""
    candidate = node_id
    while candidate not in lookup: # this will still find even if a level is missed, matching to the closest level
        shorter = re.sub(r"\([^)]+\)$", "", candidate)
        if shorter == candidate:
            return None
        candidate = shorter
    node = lookup[candidate]

    parts = []
    if h := node.get("header", "").strip():
        parts.append(f"{node['id']}: {h}")
    if node.get("level") == 0:
        if b := node.get("merged_body", "").strip():
            parts.append(b)
    else:
        for field in ("chapeau", "body"):
            if t := node.get(field, "").strip():
                parts.append(t)
        for child_id in node.get("children", []):
            child_text = node_text(child_id, lookup)
            if child_text:
                parts.append(f"{child_id} {child_text}")
        if t := node.get("continuation", "").strip():
            parts.append(t)
    return "\n".join(parts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("section")
    parser.add_argument("node_id")
    args = parser.parse_args()
    lookup = load_lookup(args.section)
    print(node_text(args.node_id, lookup))
