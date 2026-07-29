"""
Bottom-up Catala formalization pipeline for 26 USC § 7701.
"""

import json
import sys

TREE_FILE = "7701_tree.json"


# ── Tree data structure ────────────────────────────────────────────────────────

class Node:
    def __init__(self, data, parent=None):
        self.id = data["id"]
        self.num = data["num"]
        self.header = data["header"]
        self.chapeau = data["chapeau"]
        self.body = data["body"]
        self.parent = parent
        self.children = []      # list of Node
        self.catala = None      # filled in after agent call

    @property
    def is_leaf(self):
        return len(self.children) == 0

    @property
    def is_repealed(self):
        return "repealed" in self.header.lower()

    @property
    def is_crossref(self):
        return "cross reference" in self.header.lower()

    def __repr__(self):
        return f"Node({self.id!r}, children={len(self.children)})"


class Tree:
    def __init__(self, path=TREE_FILE):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.root = self._build(data, parent=None)

    def _build(self, data, parent):
        node = Node(data, parent=parent)
        for child_data in data.get("children", []):
            child = self._build(child_data, parent=node)
            node.children.append(child)
        return node

    def walk(self, node=None):
        """Yield all nodes depth-first (pre-order)."""
        if node is None:
            node = self.root
        yield node
        for child in node.children:
            yield from self.walk(child)


# ── Processing ─────────────────────────────────────────────────────────────────

def process(node, signals):
    """Recursively formalize a node bottom-up. Sets node.catala."""
    if node.is_leaf:
        node.catala = node.body

    if node.is_repealed:
        signals.append(f"REPEALED: {node.id} — {node.header}")
        node.catala = f"REPEALED: {node.id} — {node.header}"

    if node.is_crossref:
        for child in node.children:
            signals.append(f"EXTERNAL_DEPENDENCY: {child.id} {child.header}")
        node.catala = f"Cross references: {node.id}"

    for child in node.children:
        process(child, signals)

    call_agent(node, signals)


def call_agent(node, signals):
    """Placeholder — sets node.catala. Replaced by Claude CLI dispatch."""
    print(f"\n[AGENT CALL] {node.id} — {node.header}", file=sys.stderr)
    for child in node.children:
        preview = (child.catala or "")[:80].replace("\n", " ")
        print(f"  child {child.id}: {preview!r}", file=sys.stderr)
    node.catala = f"TODO: {node.id} — {node.header}"


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    tree = Tree()
    total = sum(1 for _ in tree.walk())
    print(f"Loaded: {tree.root.id}, {total} nodes", file=sys.stderr)

    signals = []
    for subsection in tree.root.children:
        process(subsection, signals)

    print("\n=== CATALA OUTPUT ===")
    for subsection in tree.root.children:
        print(subsection.catala or "")

    print("\n=== SIGNALS ===")
    for s in signals:
        print(s)


if __name__ == "__main__":
    main()
