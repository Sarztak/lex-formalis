"""
Run classify() on batch2 nodes and print construct + reason.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from formalize import TREE_FILE, Tree, classify, find_node

NODES = [
    "7701(b)(1)(A)",
    "7701(b)(1)",
    "7701(b)(2)",
    "7701(b)(3)",
    "7701(b)(4)",
    "7701(b)(9)",
    "7701(b)(10)",
    "7701(b)(5)(A)",
    "7701(b)(5)(B)",
    "7701(b)(5)(E)",
    "7701(h)(2)",
    "7701(e)",
    "7701(o)",
]


def run_one(node_id, tree):
    node = find_node(tree, node_id)
    if not node:
        return node_id, {"construct": "NOT FOUND", "reason": ""}
    result = classify(node)
    return node_id, result


if __name__ == "__main__":
    tree = Tree(TREE_FILE)
    results = {}
    with ThreadPoolExecutor(max_workers=len(NODES)) as pool:
        futures = {pool.submit(run_one, nid, tree): nid for nid in NODES}
        for fut in as_completed(futures):
            node_id, result = fut.result()
            results[node_id] = result

    for nid in NODES:
        r = results.get(nid, {})
        print(f"{nid}: [{r.get('construct','?')}]")
        print(f"  {r.get('reason','')}")
        print()
