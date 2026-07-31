"""
Bottom-up Catala formalization pipeline for 26 USC § 7701.
"""

import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime

TREE_FILE = "7701_tree.json"
PROMPT_FILE = "agent_prompt.md"
LOG_DIR = "logs"


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
        self.signals = []       # signals emitted for this node

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
    elif node.is_repealed:
        signals.append({"type": "REPEALED", "id": node.id, "header": node.header})
        node.catala = f"REPEALED: {node.id} — {node.header}"
    elif node.is_crossref:
        for child in node.children:
            term = child.header or child.body or child.id
            signals.append({"type": "EXTERNAL_DEPENDENCY", "term": term, "id": child.id})
        node.catala = f"Cross references: {node.id}"
    else:
        for child in node.children:
            process(child, signals)
        call_agent(node, signals)


def _id_to_name(node_id):
    parts = re.findall(r"[^()]+", node_id)
    return "Sec" + "_".join(parts)


def build_user_message(node):
    payload = {
        "id": node.id,
        "scope_name": _id_to_name(node.id),
        "header": node.header,
        "chapeau": node.chapeau,
        "body": node.body,
        "children": [
            {
                "id": child.id,
                "scope_name": _id_to_name(child.id),
                "header": child.header,
                "result": child.catala or "",
                "unresolved_signals": child.signals or [],
            }
            for child in node.children
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def reorder_catala(code):
    """
    Reorder catala blocks into dependency-safe order:
    1. declaration enumeration / declaration structure
    2. declaration scope
    3. scope rules
    Free text blocks kept in original relative position among non-code blocks.
    """
    blocks = [b.strip() for b in code.split("\n\n") if b.strip()]

    def block_rank(b):
        if b.startswith(("declaration enumeration", "declaration structure")):
            return 0
        if b.startswith("declaration scope"):
            return 1
        if b.startswith("scope "):
            return 2
        return 3  # free text, comments

    blocks.sort(key=block_rank)
    return "\n\n".join(blocks)


CLASSIFY_PROMPT = """\
Look at the children of this statutory provision. Do the children together form \
a set of mutually exclusive, distinct variants of the same concept — such that \
exactly one applies in any given case?

Answer with a JSON object only, no prose, no markdown fences:

{{"construct": "enumeration", "reason": "..."}}
  or
{{"construct": "not", "reason": "..."}}

Provision:
header: {header}
chapeau: {chapeau}
body: {body}
children:
{children}
"""


def classify(node):
    """Ask model: is this node an enumeration or not? Returns {"construct": ..., "reason": ...}."""
    children_text = "\n".join(
        f"  - {c.header or c.num}: {c.body or c.chapeau}"
        for c in node.children
    ) or "  (none)"
    prompt = CLASSIFY_PROMPT.format(
        header=node.header or "(none)",
        chapeau=node.chapeau or "(none)",
        body=node.body or "(none)",
        children=children_text,
    )
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", "claude-sonnet-4-6"],
        capture_output=True, text=True, timeout=60, check=False,
    )
    raw = result.stdout.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()
    try:
        parsed, _ = json.JSONDecoder().raw_decode(raw)
        return parsed
    except json.JSONDecodeError:
        return {"construct": "error", "reason": raw[:200]}


def write_log(node_id, prompt, raw_response, parsed, error=None):
    os.makedirs(LOG_DIR, exist_ok=True)
    safe_id = node_id.replace("(", "_").replace(")", "")
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(LOG_DIR, f"{safe_id}_{timestamp}.json")
    log = {
        "node_id": node_id,
        "timestamp": timestamp,
        "prompt": prompt,
        "raw_response": raw_response,
        "parsed": parsed,
        "error": error,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def call_agent(node, signals):
    with open(PROMPT_FILE, encoding="utf-8") as f:
        system_prompt = f.read()
    user_message = build_user_message(node)
    full_prompt = f"{system_prompt}\n\n---\n\nFormalize this node:\n\n{user_message}"

    print(f"[agent] {node.id} — {node.header}", file=sys.stderr)

    result = subprocess.run(
        ["claude", "-p", full_prompt, "--model", "claude-sonnet-4-6"],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )

    if result.returncode != 0:
        err = result.stderr[:500]
        print(f"  ERROR: {err}", file=sys.stderr)
        write_log(node.id, full_prompt, result.stdout, None, error=err)
        node.catala = f"# ERROR: {node.id}"
        return

    raw = result.stdout.strip()
    # model wraps output in ```json ... ``` despite being told not to
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()
    parsed = parse_response(raw)
    if parsed is None:
        print("  parse failed, attempting fix-up call", file=sys.stderr)
        write_log(node.id, full_prompt, raw, None, error="JSONDecodeError — fix-up attempted")
        raw = fixup_call(raw)
        parsed = parse_response(raw)

    if parsed is not None:
        node.catala = reorder_catala(parsed["catala"])
        node.signals = parsed.get("signals", [])
        signals.extend(node.signals)
        write_log(node.id, full_prompt, raw, {"catala": node.catala, "signals": node.signals})
    else:
        print("  fix-up also failed", file=sys.stderr)
        write_log(node.id, full_prompt, raw, None, error="JSONDecodeError — fix-up failed")
        node.catala = f"# PARSE ERROR: {node.id}"


def parse_response(raw):
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
        return response
    except json.JSONDecodeError:
        return None


def fixup_call(bad_output):
    """Model reasoned correctly but output malformed JSON. Focused reformat call."""
    fixup_prompt = (
        "The following is a Catala formalization that was not output as valid JSON.\n"
        "Reformat it into this exact structure. Raw JSON only, no markdown fences, no prose:\n\n"
        '{"catala": "... catala code ...", "signals": [{"type": "...", ...}]}\n\n'
        f"Content to reformat:\n\n{bad_output}"
    )
    result = subprocess.run(
        ["claude", "-p", fixup_prompt, "--model", "claude-sonnet-4-6"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return result.stdout.strip()


# ── Main ───────────────────────────────────────────────────────────────────────

def find_node(tree, node_id):
    for node in tree.walk(tree.root):
        if node.id == node_id:
            return node


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", help="Process a single node by id")
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
