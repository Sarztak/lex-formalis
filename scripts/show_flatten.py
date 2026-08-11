"""
Diagnose and visualize two structural patterns in a scraped IRC section tree.

Structural assumptions (validated against §101 and §7701):
  - A node has either a chapeau or a body, never both.
  - A node with a chapeau always has children; a node with children always has a chapeau.
  - A node with a body is always a leaf (no children).
  - Known exception: 101(d)(2)(B) has a chapeau that is a continuation phrase rather
    than a split signal — treated as an anomaly, not a counter-example to the rule.

Pass 1 — flatten (merge):
  A node is merged when all its children are mergeable leaves.
  A mergeable leaf has: body only — no header, no chapeau, no children.
  On merge: parent chapeau + parent body + each child's id and body + continuation
  are joined into a single body. The merged node becomes a new leaf and may itself
  be eligible for merging into its parent in the next level up.

Pass 2 — container identification (no merge):
  A node is a container when all its children are header-bearing leaves.
  A header-bearing leaf has: header + body — no chapeau, no children.
  These are independent but contextually related provisions. They are not merged;
  they are identified so they can be passed as a unit to the agent.

Output goes to logs/flatten/flatten_{section}.txt.

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


def is_mergeable_leaf(node):
    # no children, header or chapeau
    # chapeau usually means further division not having children
    # and not having should mean the same thing; this is observed
    # not proven.
    return (
        not node.get("children")
        and not node.get("header", "").strip()
        and not node.get("chapeau", "").strip()
        and bool(node.get("body", "").strip())
    )


def is_header_leaf(node):
    # no children, no chapeau -- same condition as observed
    return (
        not node.get("children")
        and not node.get("chapeau", "").strip()
        and bool(node.get("header", "").strip())
        and bool(node.get("body", "").strip())
    )


def do_merge(node):
    parts = []
    for field in ("chapeau", "body"):
        if t := node.get(field, "").strip():
            parts.append(t)
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
    """
    children = node.get("children", [])
    if not children:
        return node

    # Recurse first so children may already be merged leaves
    new_children = [flatten_recursive(c, merged_ids) for c in children]
    node = {**node, "children": new_children}

    if all(is_mergeable_leaf(c) for c in new_children):
        merged_ids.add(node["id"])
        return do_merge(node)

    return node


def identify_containers(node, container_ids):
    """Walk the original tree and collect nodes whose children are all header-bearing leaves."""
    children = node.get("children", [])
    if children:
        if all(is_header_leaf(c) for c in children):
            container_ids.add(node["id"])
        for c in children:
            identify_containers(c, container_ids)


def walk(node):
    yield node
    for child in node.get("children", []):
        yield from walk(child)


def format_container_entry(node):
    lines = []
    lines.append(f"\n{'='*70}")
    lines.append(f"{node['id']}  —  {node.get('header', '')}")
    lines.append("="*70)
    for field in ("chapeau", "body"):
        if t := node.get(field, "").strip():
            lines.append(f"  [{field}] {t[:200]}")
    for c in node.get("children", []):
        lines.append(f"  {c['id']}  —  {c['header']}")
    return "\n".join(lines)


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

    container_ids = set()
    identify_containers(merged_tree, container_ids)

    if args.node:
        merged_ids = {nid for nid in merged_ids if nid == args.node}
        container_ids = {nid for nid in container_ids if nid == args.node}

    os.makedirs(LOG_DIR, exist_ok=True)
    out_path = os.path.join(LOG_DIR, f"flatten_{args.section}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"§{args.section}: {len(merged_ids)} node(s) would be flattened\n")
        for nid in sorted(merged_ids):
            f.write(format_entry(original, merged_tree, nid) + "\n")

        f.write(f"\n\n{'#'*70}\n")
        f.write(f"CONTAINERS — {len(container_ids)} node(s) with all header-bearing leaves\n")
        f.write(f"{'#'*70}\n")
        for node in walk(merged_tree):
            if node["id"] in container_ids:
                f.write(format_container_entry(node) + "\n")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
