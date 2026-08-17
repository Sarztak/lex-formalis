"""
Build exception corpus: classify all data/*_tree.json files and extract
exception-tagged nodes into logs/exception_corpus.json for pattern analysis.

Usage:
    python scripts/build_exception_corpus.py
"""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.classify_rules import classify_node, walk_results

DATA_GLOB = "data/*_tree.json"
OUT_FILE = "logs/exception_corpus.json"
EXCEPTION_CONSTRUCTS = {"exception"}


def extract_section_id(path: str) -> str:
    return os.path.basename(path).replace("_tree.json", "")


def is_exception_node(result: dict) -> bool:
    return any(t["construct"] in EXCEPTION_CONSTRUCTS for t in result.get("tags", []))


def main():
    tree_files = sorted(glob.glob(DATA_GLOB))
    if not tree_files:
        print(f"No tree files found matching {DATA_GLOB}")
        sys.exit(1)

    corpus = []
    section_stats = {}

    for path in tree_files:
        section = extract_section_id(path)
        with open(path, encoding="utf-8") as f:
            tree = json.load(f)

        root = classify_node(tree)
        total = 0
        exceptions_found = 0

        for result in walk_results(root):
            total += 1
            if is_exception_node(result):
                exceptions_found += 1
                corpus.append({
                    "section": section,
                    "id": result["id"],
                    "header": result["header"],
                    "chapeau": result["chapeau"],
                    "body": result.get("body", ""),
                    "continuation": result.get("continuation", ""),
                    "tags": result["tags"],
                    "child_count": result["child_count"],
                })

        section_stats[section] = {"total_nodes": total, "exception_nodes": exceptions_found}
        print(f"  §{section}: {total} nodes, {exceptions_found} exception nodes")

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    output = {
        "section_stats": section_stats,
        "total_exception_nodes": len(corpus),
        "nodes": corpus,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{len(corpus)} exception nodes across {len(tree_files)} sections → {OUT_FILE}")


if __name__ == "__main__":
    main()
