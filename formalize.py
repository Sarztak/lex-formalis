"""
Bottom-up Catala formalization pipeline for 26 USC § 7701.
"""

import json
import subprocess
import sys

TREE_FILE = "7701_tree.json"
PROMPT_FILE = "agent_prompt.md"


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
        self.catala = None      # filled in after processing

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
    def __init__(self, path):
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
        # the node = None case is so that tree.walk() can start walking from root by default
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
        signals.append({"type": "REPEALED", "id": node.id, "header": node.header})
        node.catala = f"REPEALED: {node.id} — {node.header}"

    if node.is_crossref:
        for child in node.children:
            signals.append({"type": "EXTERNAL_DEPENDENCY", "term": child.header, "id": child.id})
        node.catala = f"Cross references: {node.id}"

    for child in node.children:
        process(child, signals)

    call_agent(node, signals)


def build_user_message(node):
    payload = {
        "id": node.id,
        "header": node.header,
        "chapeau": node.chapeau,
        "body": node.body,
        "children": [
            {
                "id": child.id,
                "header": child.header,
                "result": child.catala or "",
            }
            for child in node.children
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def call_agent(node, signals):
    system_prompt = open(PROMPT_FILE, encoding="utf-8").read()
    user_message = build_user_message(node)
    full_prompt = f"{system_prompt}\n\n---\n\nFormalize this node:\n\n{user_message}"

    print(f"[agent] {node.id} — {node.header}", file=sys.stderr)

    result = subprocess.run(
        ["claude", "-p", full_prompt, "--model", "claude-sonnet-4-6"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[:200]}", file=sys.stderr)
        node.catala = f"# ERROR: {node.id}"
        return

    raw = result.stdout.strip()
    # model wraps output in ```json ... ``` despite being told not to
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()
    try:
        # raw_decode instead of loads: model sometimes appends explanatory text
        # after the closing } which causes "Extra data" error with loads
        response, _ = json.JSONDecoder().raw_decode(raw)
        node.catala = response["catala"]
        signals.extend(response.get("signals", []))
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}", file=sys.stderr)
        print(f"  raw: {raw[:200]}", file=sys.stderr)
        node.catala = f"# PARSE ERROR: {node.id}"


# ── Main ───────────────────────────────────────────────────────────────────────

def find_node(tree, node_id):
    for node in tree.walk(tree.root):
        if node.id == node_id:
            return node


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", help="Process a single node by id, e.g. 7701(a)(1)")
    args = parser.parse_args()

    tree = Tree(TREE_FILE)
    total = sum(1 for _ in tree.walk(tree.root))
    print(f"Loaded: {tree.root.id}, {total} nodes", file=sys.stderr)

    signals = []

    if args.node:
        node = find_node(tree, args.node)
        if not node:
            print(f"Node {args.node} not found", file=sys.stderr)
            sys.exit(1)
        process(node, signals)
        print(node.catala)
        print(json.dumps(signals, indent=2))
    else:
        for subsection in tree.root.children:
            process(subsection, signals)

        with open("7701.catala_en", "w", encoding="utf-8") as f:
            for subsection in tree.root.children:
                f.write((subsection.catala or "") + "\n\n")
        print("Wrote 7701.catala_en", file=sys.stderr)

        with open("7701_signals.json", "w", encoding="utf-8") as f:
            json.dump(signals, f, indent=2, ensure_ascii=False)
        print(f"Wrote 7701_signals.json ({len(signals)} signals)", file=sys.stderr)


if __name__ == "__main__":
    main()
