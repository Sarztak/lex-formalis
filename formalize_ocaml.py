"""
Bottom-up OCaml formalization pipeline for 26 USC § 7701.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime

TREE_FILE = "7701_tree.json"
LOG_DIR = "logs"

with open('ocaml_system_prompt.txt', encoding='utf-8') as r:
    SYSTEM_PROMPT = r.read()

# ── Node / Tree ────────────────────────────────────────────────────────────────


class Node:
    def __init__(self, data, parent=None):
        self.id = data["id"]
        self.num = data.get("num", "")
        self.header = data.get("header", "")
        self.chapeau = data.get("chapeau", "")
        self.body = data.get("body", "")
        self.continuation = data.get("continuation", "")
        self.parent = parent
        self.children = []
        self.ocaml = None
        self.pattern = None
        self.reason = None
        self.status = None  # leaf | code | partial | ambiguous | repealed | error

    @property
    def is_leaf(self):
        return len(self.children) == 0

    @property
    def is_repealed(self):
        return "repealed" in self.header.lower()

    def raw_text(self):
        parts = []
        if self.header:
            parts.append(self.header)
        if self.chapeau:
            parts.append(self.chapeau)
        if self.body:
            parts.append(self.body)
        if self.continuation:
            parts.append(self.continuation)
        return "\n".join(parts).strip()

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
        if node is None:
            node = self.root
        yield node
        for child in node.children:
            yield from self.walk(child)

    def find(self, node_id, node=None):
        if node is None:
            node = self.root
        if node.id == node_id:
            return node
        for child in node.children:
            found = self.find(node_id, child)
            if found:
                return found
        return None


# ── Processing ─────────────────────────────────────────────────────────────────


def process(node, results):
    """Recursively formalize bottom-up. Fills node.ocaml / node.status."""
    if node.is_leaf:
        node.status = "leaf"
        return

    if node.is_repealed:
        node.status = "repealed"
        node.ocaml = f"(* REPEALED: {node.id} — {node.header} *)"
        results.append(_result_row(node, None))
        return

    for child in node.children:
        process(child, results)

    call_agent(node, results)


def _result_row(node, error):
    return {
        "id": node.id,
        "status": node.status,
        "pattern": node.pattern,
        "reason": node.reason,
        "ocaml": node.ocaml,
        "error": error,
    }


def build_user_message(node):
    payload = {
        "id": node.id,
        "header": node.header or None,
        "chapeau": node.chapeau or None,
        "body": node.body or None,
        "children": [],
    }

    for child in node.children:
        if child.status == "repealed":
            payload["children"].append({"id": child.id, "status": "repealed"})
        elif child.status == "code":
            payload["children"].append(
                {
                    "id": child.id,
                    "status": "code",
                    "pattern": child.pattern,
                    "ocaml": child.ocaml,
                }
            )
        elif child.status == "leaf":
            payload["children"].append(
                {
                    "id": child.id,
                    "status": "leaf",
                    "header": child.header or None,
                    "chapeau": child.chapeau or None,
                    "body": child.body or None,
                }
            )
        elif child.status == "partial":
            payload["children"].append(
                {
                    "id": child.id,
                    "status": "partial",
                    "reason": child.reason,
                    "header": child.header or None,
                    "chapeau": child.chapeau or None,
                    "body": child.body or None,
                }
            )
        else:
            # ambiguous or error — cross-reference or unresolvable
            payload["children"].append(
                {
                    "id": child.id,
                    "status": "ambiguous",
                    "reason": child.reason,
                    "header": child.header or None,
                    "chapeau": child.chapeau or None,
                    "body": child.body or None,
                }
            )

    return json.dumps(payload, indent=2, ensure_ascii=False)


def call_agent(node, results):
    user_message = build_user_message(node)
    full_prompt = SYSTEM_PROMPT + "\n\n---\n\n" + user_message

    print(f"[agent] {node.id} — {node.header}", file=sys.stderr)

    result = subprocess.run(
        ["claude", "-p", full_prompt, "--model", "claude-sonnet-5"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    error = None
    if result.returncode != 0:
        error = result.stderr[:500]
        print(f"  ERROR: {error}", file=sys.stderr)
        node.status = "error"
        node.ocaml = f"(* ERROR: {node.id} *)"
        write_log(node, full_prompt, result.stdout, None, error)
        results.append(_result_row(node, error))
        return

    raw = result.stdout.strip()
    parsed = parse_response(raw)

    if parsed is None:
        print("  parse failed, attempting fix-up", file=sys.stderr)
        raw2 = fixup_call(raw)
        parsed = parse_response(raw2)
        if parsed is None:
            error = "JSONDecodeError — fix-up failed"
            print("  fix-up also failed", file=sys.stderr)
            node.status = "error"
            node.ocaml = f"(* PARSE ERROR: {node.id} *)"
            write_log(node, full_prompt, raw, None, error)
            results.append(_result_row(node, error))
            return

    node.ocaml = parsed.get("ocaml", "")
    node.pattern = parsed.get("pattern", "")
    node.reason = parsed.get("reason", "")
    node.status = (
        "ambiguous"
        if node.pattern == "ambiguous"
        else ("partial" if node.pattern == "partial" else "code")
    )
    print(f"  [{node.pattern}] {node.reason}", file=sys.stderr)
    write_log(node, full_prompt, result.stdout, parsed, None)
    results.append(_result_row(node, None))


def parse_response(raw):
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()
    brace = raw.find("{")
    if brace > 0:
        raw = raw[brace:]
    try:
        parsed, _ = json.JSONDecoder().raw_decode(raw)
        return parsed
    except json.JSONDecodeError:
        return None


def fixup_call(bad_output):
    fixup_prompt = (
        "The following is an OCaml formalization that was not output as valid JSON.\n"
        "Reformat it into this exact structure. Raw JSON only, no markdown fences, no prose:\n\n"
        '{"ocaml": "...", "pattern": "disjunction|conjunction|conditional|arithmetic|mixed|wrapper|partial|ambiguous", "reason": "one sentence"}\n\n'
        f"Content to reformat:\n\n{bad_output}"
    )
    result = subprocess.run(
        ["claude", "-p", fixup_prompt, "--model", "claude-sonnet-5"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return result.stdout.strip()


def write_log(node, prompt, raw_response, parsed, error=None):
    os.makedirs(LOG_DIR, exist_ok=True)
    safe_id = node.id.replace("(", "_").replace(")", "")
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(LOG_DIR, f"ocaml_{safe_id}_{timestamp}.json")
    log = {
        "node_id": node.id,
        "timestamp": timestamp,
        "prompt": prompt,
        "raw_response": raw_response,
        "parsed": parsed,
        "error": error,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


# ── Assembly ───────────────────────────────────────────────────────────────────


def collect_ocaml(node):
    """DFS post-order: children first, then parent. Skips leaves and repealed."""
    for child in node.children:
        yield from collect_ocaml(child)
    if node.status not in ("leaf", None):
        yield node


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", help="Process single subtree by node ID")
    args = parser.parse_args()

    tree = Tree(TREE_FILE)
    total = sum(1 for _ in tree.walk())
    print(f"Loaded: {tree.root.id}, {total} nodes", file=sys.stderr)

    results = []
    ts = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    out_json = f"logs/formalize_ocaml_{ts}.json"

    if args.node:
        node = tree.find(args.node)
        if not node:
            print(f"Node {args.node} not found", file=sys.stderr)
            sys.exit(1)
        process(node, results)
        for n in collect_ocaml(node):
            if n.ocaml:
                print(n.ocaml)
                print()
    else:
        out_ml = "7701.ml"
        for subsection in tree.root.children:
            process(subsection, results)
            # write progressively so partial runs are not lost
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

        with open(out_ml, "w", encoding="utf-8") as f:
            for subsection in tree.root.children:
                for n in collect_ocaml(subsection):
                    if n.ocaml:
                        f.write(n.ocaml + "\n\n")
        print(f"Wrote {out_ml}", file=sys.stderr)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_json}", file=sys.stderr)


if __name__ == "__main__":
    main()
