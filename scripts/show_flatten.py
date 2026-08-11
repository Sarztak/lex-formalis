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
    return {
        **node,
        "chapeau": "",
        "body": "\n".join(t for t in parts if t),
        "continuation": "",
        "children": [],
    }


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


def identify_containers(node, container_map, path=None):
    """Walk the merged tree and collect nodes whose children are all header-bearing leaves.
    container_map: {node_id: [(id, header), ...]} — path from section root to container (inclusive)."""
    if path is None:
        path = []
    hdr = node.get("header", "").strip()
    current_path = path + [(node["id"], hdr)] if hdr else path
    children = node.get("children", [])
    if children:
        if all(is_header_leaf(c) for c in children):
            container_map[node["id"]] = current_path
        for c in children:
            identify_containers(c, container_map, current_path)


def identify_containers_l2(node, container_map, l2_map, path=None):
    """Find nodes (not already l1 containers) whose children are all header-bearing
    leaves or l1 containers — i.e. the parent level above the leaf containers."""
    if path is None:
        path = []
    hdr = node.get("header", "").strip()
    current_path = path + [(node["id"], hdr)] if hdr else path
    children = node.get("children", [])
    if children and node["id"] not in container_map:
        if all(is_header_leaf(c) or c["id"] in container_map for c in children):
            l2_map[node["id"]] = current_path
        for c in children:
            identify_containers_l2(c, container_map, l2_map, current_path)


def identify_containers_recursive(node, resolved, path=None):
    """
    Semantic levels: L0 = is_header_leaf, Ln = all classified children at level < n.
    Childless nodes that are not header-leaves (repealed, empty) get level None.
    resolved: {id: (path, level)}  where level is int or None.
    Returns the level of this node.
    """
    if path is None:
        path = []
    hdr = node.get("header", "").strip()
    current_path = path + [(node["id"], hdr)] if hdr else path
    children = node.get("children", [])
    if not children:
        level = 0 if is_header_leaf(node) else None
        resolved[node["id"]] = (current_path, level)
        return level
    child_levels = [identify_containers_recursive(c, resolved, current_path) for c in children]
    classified = [l for l in child_levels if l is not None]
    my_level = (max(classified) + 1) if classified else None
    resolved[node["id"]] = (current_path, my_level)
    return my_level


def walk(node):
    yield node
    for child in node.get("children", []):
        yield from walk(child)


def format_recursive_entry(node, path, level, resolved):
    lines = []
    lines.append(f"\n{'='*70}")
    lines.append(f"[L{level}]  " + "  >  ".join(f"{nid}: {hdr}" for nid, hdr in path))
    lines.append("=" * 70)
    if t := node.get("chapeau", "").strip():
        lines.append(f"  [chapeau] {t[:200]}")
    if t := node.get("continuation", "").strip():
        lines.append(f"  [continuation] {t[:200]}")
    for c in node.get("children", []):
        clevel = resolved.get(c["id"], (None, None))[1]
        tag = f"[L{clevel}]" if clevel is not None else "[?]"
        lines.append(f"  {c['id']}  —  {tag}  {c.get('header', '')}")
    return "\n".join(lines)


def format_container_l2_entry(node, path, container_map):
    lines = []
    lines.append(f"\n{'='*70}")
    lines.append("  >  ".join(f"{nid}: {hdr}" for nid, hdr in path))
    lines.append("=" * 70)
    for c in node.get("children", []):
        if c["id"] in container_map:
            lines.append(f"  {c['id']}  —  [container] {c.get('header', '')}")
            for gc in c.get("children", []):
                lines.append(f"    {gc['id']}  —  {gc.get('header', '')}")
        else:
            lines.append(f"  {c['id']}  —  [leaf] {c.get('header', '')}")
    return "\n".join(lines)


def format_container_entry(node, path):
    lines = []
    lines.append(f"\n{'='*70}")
    lines.append("  >  ".join(f"{nid}: {hdr}" for nid, hdr in path))
    lines.append("=" * 70)
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
    lines.append("=" * 70)

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

    container_map = {}
    identify_containers(merged_tree, container_map)

    if args.node:
        merged_ids = {nid for nid in merged_ids if nid == args.node}
        container_map = {nid: p for nid, p in container_map.items() if nid == args.node}

    os.makedirs(LOG_DIR, exist_ok=True)
    out_path = os.path.join(LOG_DIR, f"flatten_{args.section}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"§{args.section}: {len(merged_ids)} node(s) would be flattened\n")
        for nid in sorted(merged_ids):
            f.write(format_entry(original, merged_tree, nid) + "\n")

        f.write(f"\n\n{'#'*70}\n")
        f.write(f"CONTAINERS — {len(container_map)} node(s) with all header-bearing leaves\n")
        f.write(f"{'#'*70}\n")
        for node in walk(merged_tree):
            if node["id"] in container_map:
                f.write(format_container_entry(node, container_map[node["id"]]) + "\n")

        l2_map = {}
        identify_containers_l2(merged_tree, container_map, l2_map)
        if args.node:
            l2_map = {nid: p for nid, p in l2_map.items() if nid == args.node}

        f.write(f"\n\n{'#'*70}\n")
        f.write(f"CONTAINER L2 — {len(l2_map)} node(s): mixed header-leaves + containers\n")
        f.write(f"{'#'*70}\n")
        for node in walk(merged_tree):
            if node["id"] in l2_map:
                f.write(format_container_l2_entry(node, l2_map[node["id"]], container_map) + "\n")

        resolved = {}
        identify_containers_recursive(merged_tree, resolved)
        containers_all = {nid: info for nid, info in resolved.items() if info[1] is not None and info[1] > 0}
        if args.node:
            containers_all = {nid: info for nid, info in containers_all.items() if nid == args.node}

        f.write(f"\n\n{'#'*70}\n")
        f.write(f"RECURSIVE STRUCTURE — {len(containers_all)} container(s) (all depths)\n")
        f.write(f"{'#'*70}\n")
        for node in walk(merged_tree):
            if node["id"] in containers_all:
                path, level = containers_all[node["id"]]
                f.write(format_recursive_entry(node, path, level, resolved) + "\n")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
