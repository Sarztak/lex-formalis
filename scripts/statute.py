import argparse
import copy
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


def build_child_map(lookup):
    child_map = {}
    for node in lookup.values():
        for child_id in node.get("children", []):
            child_map[child_id] = node["id"]
    return child_map


def node_text(node_id, lookup, child_map=None):
    if node_id in lookup:
        node = lookup[node_id]
    elif child_map and node_id in child_map:
        node = lookup[child_map[node_id]]
    else:
        raise KeyError(f"Node {node_id!r} not found in lookup or child_map")

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
            _, child_text = node_text(child_id, lookup, child_map)
            parts.append(f"{child_text}")
        if t := node.get("continuation", "").strip():
            parts.append(t)
    return node["id"], "\n".join(parts)


def get_parent(node_id, lookup):
    shorter = re.sub(r"\([^)]+\)$", "", node_id)
    if shorter == node_id or shorter not in lookup:
        raise KeyError(f"Parent not found for {node_id!r}")
    return lookup[shorter]


def build_context(node_id, lookup, child_map):
    """Return (node_text, preceding_siblings_context) for any node."""
    resolved_id, text = node_text(node_id, lookup, child_map)

    parent = get_parent(resolved_id, lookup)
    children = parent.get("children", [])
    idx = children.index(resolved_id)

    truncated_parent = copy.copy(parent)
    truncated_parent["children"] = children[:idx]
    _, parent_context = node_text(parent["id"], {**lookup, parent["id"]: truncated_parent}, child_map)

    return text, parent_context


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("section")
    parser.add_argument("node_id")
    args = parser.parse_args()
    lookup = load_lookup(args.section)
    child_map = build_child_map(lookup)
    _, text = node_text(args.node_id, lookup, child_map)
    print(text)
