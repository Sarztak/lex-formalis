"""
Show which nodes would be flattened under P1, with recursive bottom-up merging.

Rule: if all children of a node are leaves whose body starts with a lowercase
letter, merge them into the parent (including the parent's continuation).
The merged parent is now itself a leaf. If its merged body also starts with
lowercase, it is eligible to be merged into its own parent by the same rule —
applied bottom-up until nothing changes.

Usage:
    python scripts/show_flatten.py 101
    python scripts/show_flatten.py 101 101(d)(2)(B)
"""

import argparse
import copy
import json
import os
import sys

LOG_DIR = "logs/flatten"


def load_tree(section):
    path = f"data/{section}_tree.json"
    if not os.path.exists(path):
        sys.exit(f"Tree not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_leaf(node):
    return not node.get("children")


def starts_lowercase(node):
    t = node.get("body", "").strip()
    return bool(t) and not t[0].isupper()


def do_merge(node):
    parts = [node.get("chapeau", "").strip()]
    for child in node.get("children", []):
        if t := child.get("body", "").strip():
            parts.append(f"{child['id']} {t}")
    if cont := node.get("continuation", "").strip():
        parts.append(cont)
    return {**node, "chapeau": "", "body": "\n".join(t for t in parts if t), "continuation": "", "children": []}


def flatten_recursive(node, merged_ids):
    """
    Bottom-up recursive flatten. Returns transformed node.
    Records the id of every node that gets merged into.
    The logic is chapeau signal a potential splitting, body doesn't, so we check if a chapeau exists and if all children are leaf nodes and they start with a lower case letter or not, if so then we merge considering that it is part of the same chapeau.
    """
    children = node.get("children", [])
    if not children:
        return node

    # Recurse first so children may already be merged leaves
    new_children = [flatten_recursive(c, merged_ids) for c in children]
    node = {**node, "children": new_children}

    if node.get("chapeau", "").strip() and all(is_leaf(c) and starts_lowercase(c) for c in new_children):
        merged_ids.add(node["id"])
        return do_merge(node)

    return node


def walk(node):
    yield node
    for child in node.get("children", []):
        yield from walk(child)


def format_entry(original, merged, node_id):
    orig_node = next((n for n in walk(original) if n["id"] == node_id), None)
    merged_node = next((n for n in walk(merged) if n["id"] == node_id), None)
    if not orig_node or not merged_node:
        return ""

    lines = []
    lines.append(f"\n{'='*70}")
    lines.append(f"{node_id}  —  {orig_node.get('header', '')}")
    lines.append("="*70)

    lines.append("\n--- BEFORE ---")
    for field in ("chapeau", "body", "continuation"):
        if t := orig_node.get(field, "").strip():
            lines.append(f"  [{field}] {t[:200]}")
    for c in orig_node.get("children", []):
        label = c["id"] + (f" — {c['header']}" if c.get("header") else "")
        lines.append(f"  {label}")
        for field in ("chapeau", "body"):
            if t := c.get(field, "").strip():
                lines.append(f"    {t[:120]}")

    lines.append("\n--- AFTER ---")
    lines.append(f"  [body] {merged_node.get('body', '').strip()}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("section")
    parser.add_argument("node", nargs="?")
    args = parser.parse_args()

    original = load_tree(args.section)
    merged_ids = set()
    merged_tree = flatten_recursive(copy.deepcopy(original), merged_ids)

    if args.node:
        merged_ids = {nid for nid in merged_ids if nid == args.node}

    os.makedirs(LOG_DIR, exist_ok=True)
    out_path = os.path.join(LOG_DIR, f"flatten_{args.section}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"§{args.section}: {len(merged_ids)} node(s) would be flattened\n")
        for nid in sorted(merged_ids):
            f.write(format_entry(original, merged_tree, nid) + "\n")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
