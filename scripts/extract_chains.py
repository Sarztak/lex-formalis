"""
Extract exception chains from a section.

Pipeline:
  1. pipeline/classify_rules.py {section}  → logs/classify/classify_rules_{section}.json
  2. pipeline/resolve_refs.py {section}    → logs/resolve/resolve_refs_{section}.txt
  3. this script                           → logs/chains/{section}_chains.json

Reads classify log to find exception-tagged nodes.
Reads resolve_refs log to get within-section [OK] cross-references.
Builds undirected adjacency list from exception nodes and their OK targets.
Finds connected components — each component with at least one exception node is a candidate chain (base rule + exception(s)).
Exceptions with no within-section refs are dropped.

Usage:
    python scripts/extract_chains.py 7701
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

CLASSIFY_DIR = "logs/classify"
RESOLVE_DIR = "logs/resolve"
LOG_DIR = "logs/chains"

# Parses: [7701(b)(3)(B)] [body] "subparagraph (A)" → 7701(b)(3)(A) [OK|MISSING]
REF_LINE = re.compile(r"^\[([^\]]+)\] \[[^\]]+\] \"[^\"]+\" → (\S+) \[(?:OK|MISSING)\]$")


def load_exception_ids(section):
    path = os.path.join(CLASSIFY_DIR, f"classify_rules_{section}.json")
    if not os.path.exists(path):
        sys.exit(f"Missing: {path} — run pipeline/classify_rules.py {section} first")
    with open(path) as f:
        data = json.load(f)
    return {
        node["id"]
        for node in data["results"]
        if any(t["construct"] == "exception" for t in node.get("tags", []))
    }


def load_refs(section):
    """Parse resolve_refs log → {source_id: [target_id, ...]} for all refs."""
    path = os.path.join(RESOLVE_DIR, f"resolve_refs_{section}.txt")
    if not os.path.exists(path):
        sys.exit(f"Missing: {path} — run pipeline/resolve_refs.py {section} first")
    refs = defaultdict(list)
    with open(path) as f:
        for line in f:
            m = REF_LINE.match(line.strip())
            if m:
                src, tgt = m.group(1), m.group(2)
                if src != tgt:
                    refs[src].append(tgt)
    return refs


def exception_subgraph(exception_ids, all_refs):
    """Subgraph of exception nodes + nodes they directly reference (outgoing only)."""
    subgraph_nodes = set(exception_ids) & set(all_refs)
    for eid in list(subgraph_nodes):
        subgraph_nodes |= set(all_refs.get(eid, []))
    sub = defaultdict(set)
    for node in subgraph_nodes:
        for tgt in all_refs.get(node, []):
            if tgt in subgraph_nodes:
                sub[node].add(tgt)
                sub[tgt].add(node)
    return sub


def connected_components(adj):
    parent = {node: node for node in adj}

    def find(node):
        while parent[node] != node:
            node = parent[node]
        return node

    for src, targets in adj.items():
        for tgt in targets:
            root_s, root_t = find(src), find(tgt)
            if root_s != root_t:
                parent[root_s] = root_t

    groups = defaultdict(list)
    for node in adj:
        groups[find(node)].append(node)
    return list(groups.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("section")
    args = parser.parse_args()

    exception_ids = load_exception_ids(args.section)
    all_refs = load_refs(args.section)

    # Build undirected adj list from all nodes and all their refs
    adj = defaultdict(set)
    for src, targets in all_refs.items():
        for tgt in targets:
            adj[src].add(tgt)
            adj[tgt].add(src)

    # Track which exception nodes appear in the graph at all
    active_exception_ids = exception_ids & set(all_refs.keys())
    dropped = len(exception_ids) - len(active_exception_ids)

    sub = exception_subgraph(active_exception_ids, all_refs)
    components = connected_components(sub)

    # Keep components containing at least one exception node with refs
    chains = []
    for comp in components:
        comp_exceptions = [n for n in comp if n in active_exception_ids]
        if not comp_exceptions:
            continue
        sorted_nodes = sorted(comp, key=lambda x: (len(x), x))
        chains.append({
            "nodes": sorted_nodes,
            "exception_nodes": sorted(comp_exceptions, key=lambda x: (len(x), x)),
            "edges": {src: list(sub[src]) for src in sorted_nodes},
        })

    chains.sort(key=lambda c: (len(c["nodes"][0]), c["nodes"][0]))

    os.makedirs(LOG_DIR, exist_ok=True)
    out_path = os.path.join(LOG_DIR, f"{args.section}_chains.json")
    with open(out_path, "w") as f:
        json.dump({"section": args.section, "chains": chains}, f, indent=2)

    print(f"{len(exception_ids)} exception nodes, {dropped} dropped (no within-section refs)")
    print(f"{len(chains)} chains\n")
    for i, chain in enumerate(chains):
        print(f"Chain {i+1}: {chain['nodes']}")
        print(f"  exceptions: {chain['exception_nodes']}")
        for src, targets in chain["edges"].items():
            print(f"  {src} → {targets}")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
