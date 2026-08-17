"""
Extract exception chains from a section.

Pipeline:
  1. pipeline/classify_rules.py {section}  → logs/classify/classify_rules_{section}.json
  2. pipeline/resolve_refs.py {section}    → logs/resolve/resolve_refs_{section}.txt
  3. this script                           → logs/chains/{section}_chains.json

Reads classify log to find exception-tagged nodes.
Reads resolve_refs log to get all cross-references.
Builds undirected adjacency list and finds connected components.
Each component with at least one exception node is a candidate chain.

Usage:
    python scripts/extract_chains.py 7701
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

_ROMAN = {r: i for i, r in enumerate(
    ['i','ii','iii','iv','v','vi','vii','viii','ix','x',
     'xi','xii','xiii','xiv','xv','xvi','xvii','xviii','xix','xx'], 1
)}

def _node_key(node_id):
    m = re.match(r'^(\d+)', node_id)
    section = int(m.group(1)) if m else 0
    parts = re.findall(r'\(([^)]+)\)', node_id)
    key = [(section, '')]
    for idx, p in enumerate(parts):
        if p.isdigit():
            key.append((int(p), ''))
        elif idx in (3, 4) and p.lower() in _ROMAN:
            key.append((_ROMAN[p.lower()], ''))
        else:
            key.append((0, p.lower()))
    return key


CLASSIFY_DIR = "logs/classify"
RESOLVE_DIR = "logs/resolve"
LOG_DIR = "logs/chains"

# Parses: [7701(b)(3)(B)] [body] "subparagraph (A)" → 7701(b)(3)(A) [OK|MISSING]
REF_LINE = re.compile(
    r"^\[([^\]]+)\] \[[^\]]+\] \"[^\"]+\" → (\S+) \[(?:OK|MISSING)\]$"
)


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

    adj = defaultdict(set)
    for src, targets in all_refs.items():
        for tgt in targets:
            adj[src].add(tgt)
            adj[tgt].add(src)

    components = connected_components(adj)

    chains = []
    for comp in components:
        comp_exceptions = [n for n in comp if n in exception_ids]
        if not comp_exceptions:
            continue
        sorted_nodes = sorted(comp, key=_node_key)
        chains.append(
            {
                "nodes": sorted_nodes,
                "exception_nodes": sorted(comp_exceptions, key=_node_key),
                "edges": {src: list(adj[src]) for src in sorted_nodes},
            }
        )

    chains.sort(key=lambda c: _node_key(c["nodes"][0]))

    os.makedirs(LOG_DIR, exist_ok=True)
    out_path = os.path.join(LOG_DIR, f"{args.section}_chains.json")
    with open(out_path, "w") as f:
        json.dump({"section": args.section, "chains": chains}, f, indent=2)

    print(f"{len(exception_ids)} exception nodes")
    print(f"{len(chains)} chains\n")
    for i, chain in enumerate(chains):
        print(f"Chain {i+1}: {chain['nodes']}")
        print(f"  exceptions: {chain['exception_nodes']}")
        for src, targets in chain["edges"].items():
            print(f"  {src} → {targets}")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
