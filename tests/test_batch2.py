"""
Batch test 2: § 7701 (b) subsections, (e), (h)(2), (o), (p).
Writes batch_results2.json — does not overwrite batch_results.json.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from formalize import Tree, find_node, process, TREE_FILE

NODES = [
    "7701(b)(1)",
    "7701(b)(2)",
    "7701(b)(3)",
    "7701(b)(4)",
    "7701(b)(9)",
    "7701(b)(10)",
    "7701(b)(5)(A)",
    "7701(b)(5)(B)",
    "7701(b)(5)(E)",
    "7701(e)",
    "7701(h)(2)",
    "7701(o)",
    "7701(p)",
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
    with open("batch_results2.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Wrote batch_results2.json ({len(results)} nodes, {len(all_signals)} signals)")
