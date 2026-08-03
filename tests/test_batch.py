"""
Batch test: run formalize pipeline on selected § 7701 nodes in parallel.
Each input gets its own tree instance to avoid shared state.
Writes batch_results.json.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from formalize import Tree, find_node, process, TREE_FILE

NODES = [
    "7701(a)(11)",
    "7701(a)(12)",
    "7701(a)(19)(C)",
    "7701(a)(19)",
    "7701(a)(30)",
    "7701(a)(31)",
    "7701(a)(32)",
    "7701(a)(33)(A)",
    "7701(a)(33)",
    "7701(a)(36)",
    "7701(a)(37)",
    "7701(a)(51)(C)",
    "7701(a)(49)",
    "7701(a)(51)(D)(i)",
    "7701(a)(51)(E)",
]


def run_one(node_id):
    tree = Tree(TREE_FILE)
    node = find_node(tree, node_id)
    if not node:
        print(f"NOT FOUND: {node_id}", file=sys.stderr)
        return node_id, {"catala": "# NOT FOUND", "signals": []}
    signals = []
    process(node, signals)
    return node_id, {"catala": node.catala, "signals": signals}


if __name__ == "__main__":
    results = {}
    with ThreadPoolExecutor(max_workers=len(NODES)) as pool:
        futures = {pool.submit(run_one, nid): nid for nid in NODES}
        for fut in as_completed(futures):
            node_id, result = fut.result()
            results[node_id] = result

    all_signals = [s for r in results.values() for s in r["signals"]]
    with open("batch_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Wrote batch_results.json ({len(results)} nodes, {len(all_signals)} signals)")
