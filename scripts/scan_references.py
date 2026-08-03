"""
Scan all nodes in 7701_tree.json for cross-reference lines.
Outputs every unique line containing paragraph/subparagraph/clause/subclause/item/subitem/section/subsection.
"""

import json
import os
import re

TREE_FILE = "data/7701_tree.json"
OUT_FILE = "logs/scan/scan_references.txt"

PATTERN = re.compile(
    r"[^\n]*\b(paragraph|subparagraph|clause|subclause|item|subitem|section|subsection)\b[^\n]*",
    re.IGNORECASE,
)


def walk(node):
    yield node
    for c in node.get("children", []):
        yield from walk(c)


def main():
    with open(TREE_FILE, encoding="utf-8") as f:
        data = json.load(f)

    results = []
    seen_lines = set()

    for node in walk(data):
        node_id = node["id"]
        for field in ("header", "chapeau", "body", "continuation"):
            text = node.get(field) or ""
            for m in PATTERN.finditer(text):
                line = m.group(0).strip()
                key = (node_id, field, line)
                if key not in seen_lines:
                    seen_lines.add(key)
                    results.append((node_id, field, line))

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for node_id, field, line in results:
            f.write(f"[{node_id}] [{field}] {line}\n")

    print(f"Found {len(results)} reference lines → {OUT_FILE}")


if __name__ == "__main__":
    main()
