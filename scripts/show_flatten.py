"""
Flatten and level IRC section trees for downstream pipeline use.

Pass 1 — flatten (merge):
  A node is merged when all its children are mergeable leaves.
  A mergeable leaf has: body only — no header, no chapeau, no children.
  On merge: parent chapeau + parent body + each child's body + continuation
  are joined into a single body. The merged node becomes a new leaf and may itself
  be eligible for merging into its parent in the next level up.

Pass 2 — recursive level assignment:
  L0 = header leaf (no children, no chapeau, has header or body).
  Ln = node whose classified children are all at level < n.
  Nodes with no classifiable children (repealed, empty) get level None.

Outputs:
  logs/flatten/flatten_{section}.txt   — diagnostic view of merged + leveled structure
  logs/flatten/merged_{section}.json   — all L0 leaves + containers (L1+), sorted level desc

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


def is_mergeable_leaf(node):
    return (
        not node.get("children")
        and not node.get("header", "").strip()
        and not node.get("chapeau", "").strip()
        and bool(node.get("body", "").strip())
    )


def is_header_leaf(node):
    return (
        not node.get("children")
        and not node.get("chapeau", "").strip()
        # for repealed sections only header exists.
        and (bool(node.get("header", "").strip()) or bool(node.get("body", "").strip()))
    )


def do_merge(node):
    parts = []
    for field in ("chapeau", "body"):
        if t := node.get(field, "").strip():
            parts.append(t)
    for child in node.get("children", []):
        if t := child.get("body", "").strip():
            parts.append(t)
    if cont := node.get("continuation", "").strip():
        parts.append(cont)
    return {
        **node,
        "chapeau": "",
        "body": "\n".join(t for t in parts if t),
        "continuation": "",
        "children": [],
    }


def flatten_recursive(node, merged_ids, merged_data):
    children = node.get("children", [])
    if not children:
        return node

    new_children = [flatten_recursive(c, merged_ids, merged_data) for c in children]
    node = {**node, "children": new_children}

    if all(is_mergeable_leaf(c) for c in new_children):
        merged_ids.add(node["id"])
        merged_node = do_merge(node)
        merged_data[node["id"]] = {
            "id": node["id"],
            "header": node.get("header", "").strip(),
            "merged_body": merged_node["body"],
            "children": [c["id"] for c in new_children],
        }
        return merged_node

    return node


def identify_containers_recursive(node, resolved, path=None):
    """
    L0 = is_header_leaf, Ln = max(child levels) + 1.
    Nodes with no classifiable children get level None.
    resolved: {id: (path, level)}
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
        if clevel == 0:
            if body := c.get("body", "").strip():
                lines.append(f"    {body}")
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
    merged_data = {}
    merged_tree = flatten_recursive(copy.deepcopy(original), merged_ids, merged_data)

    resolved = {}
    identify_containers_recursive(merged_tree, resolved)

    if args.node:
        merged_ids = {nid for nid in merged_ids if nid == args.node}

    containers_all = {nid: info for nid, info in resolved.items() if info[1] is not None and info[1] > 0}
    if args.node:
        containers_all = {nid: info for nid, info in containers_all.items() if nid == args.node}

    os.makedirs(LOG_DIR, exist_ok=True)
    out_path = os.path.join(LOG_DIR, f"flatten_{args.section}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"§{args.section}: {len(merged_ids)} node(s) would be flattened\n")
        for nid in sorted(merged_ids):
            f.write(format_entry(original, merged_tree, nid) + "\n")

        f.write(f"\n\n{'#'*70}\n")
        f.write(f"RECURSIVE STRUCTURE — {len(containers_all)} container(s) (all depths)\n")
        f.write(f"{'#'*70}\n")
        for node in walk(merged_tree):
            if node["id"] in containers_all:
                path, level = containers_all[node["id"]]
                f.write(format_recursive_entry(node, path, level, resolved) + "\n")

    for node in walk(original):
        if is_header_leaf(node) and node["id"] not in merged_data:
            merged_data[node["id"]] = {
                "id": node["id"],
                "header": node.get("header", "").strip(),
                "merged_body": node.get("body", "").strip(),
                "children": [],
            }

    containers = []
    for node in walk(merged_tree):
        level = resolved.get(node["id"], (None, None))[1]
        if level is None or level == 0:
            continue
        containers.append({
            "id": node["id"],
            "level": level,
            "header": node.get("header", "").strip(),
            "chapeau": node.get("chapeau", "").strip(),
            "body": node.get("body", "").strip(),
            "continuation": node.get("continuation", "").strip(),
            "children": [c["id"] for c in node.get("children", [])],
        })

    leaves = [{"level": 0, **e} for e in merged_data.values()]
    all_nodes = sorted(leaves + containers, key=lambda n: n["level"], reverse=True)

    merged_json_path = os.path.join(LOG_DIR, f"merged_{args.section}.json")
    with open(merged_json_path, "w", encoding="utf-8") as f:
        json.dump(
            {"section": args.section, "nodes": all_nodes},
            f, indent=2, ensure_ascii=False,
        )
    print(f"Wrote {out_path}")
    print(f"Wrote {merged_json_path}")


if __name__ == "__main__":
    main()
