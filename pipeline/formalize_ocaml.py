"""
Bottom-up OCaml formalization pipeline for 26 USC § 7701.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import deque
from datetime import UTC, datetime

from resolve_refs import find_refs

TREE_FILE = "data/7701_tree.json"
LOG_DIR = "logs/formalize"
_CLASSIFY_LOG_DIR = "logs/classify"

with open("prompts/ocaml_system_prompt.txt", encoding="utf-8") as r:
    SYSTEM_PROMPT = r.read()

with open("prompts/type_system_prompt.txt", encoding="utf-8") as r:
    TYPE_SYSTEM_PROMPT = r.read()

# ── Node / Tree ────────────────────────────────────────────────────────────────


class Node:
    def __init__(self, data, parent=None):
        self.id = data["id"]
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


_EXCEPTION_HEADER_KW = [
    "exception",
    "not to apply",
    "nonapplication",
    "shall not apply",
    "inapplicability",
]
_EXCEPTION_CHAPEAU_KW = ["shall not apply", "does not apply"]


def _is_exception_provision(data):
    header = (data.get("header") or "").lower()
    chapeau = (data.get("chapeau") or "").lower()
    return (
        any(kw in header for kw in _EXCEPTION_HEADER_KW)
        or any(kw in chapeau for kw in _EXCEPTION_CHAPEAU_KW)
    ) and bool(data.get("children"))


def _flatten_children(data):
    parts = []
    for child in data.get("children", []):
        _flatten_children(child)
        for field in ("chapeau", "body", "continuation"):
            t = (child.get(field) or "").strip()
            if t:
                parts.append(t)
    existing = (data.get("body") or "").strip()
    extra = " ".join(parts)
    data["body"] = (existing + " " + extra).strip() if existing else extra
    data["children"] = []


def _preprocess_tree(data):
    if _is_exception_provision(data):
        _flatten_children(data)
    else:
        for child in data.get("children", []):
            _preprocess_tree(child)


class Tree:
    def __init__(self, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        _preprocess_tree(data)
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


# ── Dependency graph + topological sort ────────────────────────────────────────


def build_dep_graph(tree):
    """
    Returns deps: {node_id: set of node_ids this node must be processed after}.
    Edges come from two sources:
      - structural: parent depends on each child (children processed first)
      - cross-refs: resolved via find_refs on all text fields
    """
    nodes = list(tree.walk())
    all_ids, deps = set(), {}
    for node in nodes:
        all_ids.add(node.id)
        deps[node.id] = set()

    def ancestor_ids(node):
        ids = set()
        p = node.parent
        while p:
            ids.add(p.id)
            p = p.parent
        return ids

    for node in nodes:
        for child in node.children:
            deps[node.id].add(child.id)
        anc = ancestor_ids(node)
        for field in ("header", "chapeau", "body", "continuation"):
            text = getattr(node, field) or ""
            for _, target in find_refs(node.id, text):
                if target in all_ids and target != node.id and target not in anc:
                    deps[node.id].add(target)
    return deps


def topo_sort(deps, depth_map=None):
    """
    Kahn's algorithm over deps: {node_id: set of node_ids it depends on}.
    Nodes with no unresolved dependencies are queued first; as each node is
    emitted, in_degree of its dependents decrements and newly-ready nodes join
    the queue. Nodes whose in_degree never reaches 0 are in a dependency cycle
    and cannot be ordered — they are appended at the end sorted by depth
    (deepest first) so parents still come after children within the cycle group.
    """
    dependents = {nid: set() for nid in deps}
    in_degree = {nid: 0 for nid in deps}

    for nid, needed in deps.items():
        for target in needed:
            dependents[target].add(nid)
            in_degree[nid] += 1

    queue = deque(nid for nid, d in in_degree.items() if d == 0)
    order = []

    while queue:
        nid = queue.popleft()
        order.append(nid)
        for dep in dependents[nid]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    cycles = [nid for nid, d in in_degree.items() if d > 0]
    if cycles:
        print(
            f"WARNING: {len(cycles)} nodes in dependency cycle: {cycles}",
            file=sys.stderr,
        )
        if depth_map:
            cycles.sort(key=lambda nid: -depth_map.get(nid, 0))
        order.extend(cycles)

    return order


# ── Checker agent ─────────────────────────────────────────────────────────────

_CHECKER_SYSTEM = (
    "You are a code reviewer for OCaml formalizations of US tax law provisions.\n"
    "You receive provision text, generated OCaml, and rules to verify.\n"
    'Return JSON only: {"pass": true} if all rules satisfied, '
    'or {"pass": false, "issues": "specific problems"} if any rule is violated.'
)


def _sanitize_section_id(section_id):
    s = section_id.lower()
    s = s.replace(".", "")
    s = re.sub(r"[()]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return "sec_" + s


def _node_is_exception(node):
    header = (node.header or "").lower()
    chapeau = (node.chapeau or "").lower()
    return any(kw in header for kw in _EXCEPTION_HEADER_KW) or any(
        kw in chapeau for kw in _EXCEPTION_CHAPEAU_KW
    )


def _external_crossrefs(node, all_ids):
    seen, result = set(), []
    for field in ("header", "chapeau", "body", "continuation"):
        text = getattr(node, field) or ""
        for _, target_id in find_refs(node.id, text):
            if target_id not in all_ids and target_id not in seen:
                seen.add(target_id)
                result.append((target_id, _sanitize_section_id(target_id)))
    return result


def _run_checker(node, ocaml, all_ids):
    ext_refs = _external_crossrefs(node, all_ids)
    is_exc = _node_is_exception(node)
    if not ext_refs and not is_exc:
        return True, None

    rules = []
    for target_id, param_name in ext_refs:
        rules.append(
            f"- Cross-reference to §{target_id} must appear as parameter "
            f"`{param_name} : bool` in the OCaml."
        )
    if is_exc:
        rules.append(
            "- Exception provision: each exception must be a standalone top-level function. "
            "Module body must only alias existing top-level functions using `let name = name` — "
            "no new function definitions inside the module."
        )

    user_msg = (
        f"Provision text:\n{node.raw_text()}\n\n"
        f"Generated OCaml:\n```ocaml\n{ocaml}\n```\n\n"
        f"Rules to verify:\n" + "\n".join(rules) + "\n\n"
        'Return JSON only: {"pass": true} or {"pass": false, "issues": "..."}'
    )

    result = subprocess.run(
        [
            "claude",
            "-p",
            _CHECKER_SYSTEM + "\n\n" + user_msg,
            "--model",
            "claude-sonnet-5",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        return True, None
    parsed = parse_response(result.stdout.strip())
    if parsed is None or parsed.get("pass"):
        return True, None
    return False, parsed.get("issues", "checker found issues")


# ── Processing ─────────────────────────────────────────────────────────────────


def process_flat(nodes_in_order, deps, results, tags=None, type_preamble=None):
    """
    Process nodes in topological order (dependencies first).
    tags: {node_id: set of construct strings} from classify_rules output.
    type_preamble: shared OCaml type declarations prepended to every agent prompt.
    Leaf nodes without a 'definition' tag are clause fragments — marked partial
    without an agent call since they produce no reusable OCaml.
    """
    if tags is None:
        tags = {}
    formalized = {}  # node_id -> (node_id, header, ocaml)
    all_ids = {n.id for n in nodes_in_order}

    for node in nodes_in_order:
        if node.is_repealed:
            node.status = "repealed"
            node.ocaml = f"(* REPEALED: {node.id} — {node.header} *)"  # output marker in .ml file
            results.append(_result_row(node, None))
            continue  # build_user_message shows "[REPEALED]" to agent, not this OCaml comment

        if node.is_leaf:
            node_tags = tags.get(node.id, set())
            if "definition" in node_tags:
                node.status = "definition"
                node.pattern = "definition"
                node.reason = (
                    "terminal definition — type declared in shared types.ml preamble"
                )
            else:
                node.status = "partial"
                node.pattern = "partial"
                node.reason = (
                    "leaf clause fragment — completes at containing provision level"
                )
            results.append(_result_row(node, None))
            continue

        child_ids = {c.id for c in node.children}
        context = {
            nid: formalized[nid]
            for nid in deps.get(node.id, set())
            if nid not in child_ids and nid in formalized
        }

        call_agent(node, results, context, type_preamble, all_ids)

        if node.status in ("code", "ambiguous") and node.ocaml:
            formalized[node.id] = (node.id, node.header, node.ocaml)


def _result_row(node, error):
    return {
        "id": node.id,
        "status": node.status,
        "pattern": node.pattern,
        "reason": node.reason,
        "ocaml": node.ocaml,
        "error": error,
    }


def _child_text(child):
    """Full provision text of a child node, newline-joined."""
    parts = []
    label = f"{child.id}" + (f" — {child.header}" if child.header else "")
    parts.append(label)
    if child.chapeau:
        parts.append(child.chapeau)
    if child.body:
        parts.append(child.body)
    if child.continuation:
        parts.append(child.continuation)
    return "\n".join(parts)


def build_user_message(node, context=None, type_preamble=None):
    parts = []

    if type_preamble:
        parts.append(
            "The following OCaml types are shared across all provisions — do NOT redefine them:\n"
            f"```ocaml\n{type_preamble}\n```\n"
        )

    # resolved cross-references available from already-processed siblings/ancestors
    if context:
        parts.append(
            "The following sections are already formalized and available as helpers:"
        )
        for node_id, header, ocaml in context.values():
            label = f"{node_id}" + (f" — {header}" if header else "")
            parts.append(
                f"\n{label}\n```<sub-provision-code>\n{ocaml}\n```</sub-provision-code>"
            )
        parts.append("\n---")

    # parent's own provision text (header, chapeau, body — continuation comes after children)
    label = f"{node.id}" + (f" — {node.header}" if node.header else "")
    parts.append(label)
    if node.chapeau:
        parts.append(node.chapeau)
    if node.body:
        parts.append(node.body)

    for child in node.children:
        if child.status == "repealed":
            # build_user_message shows "[REPEALED]" to agent, not the OCaml comment set to node.ocaml for repealed sections
            parts.append(f"\n{child.id} — [REPEALED]")
        elif child.status == "ambiguous" and not child.ocaml:
            # should not happen — prompt requires all ambiguous nodes to produce a stub
            parts.append(
                f"\n{child.id}"
                + (f" — {child.header}" if child.header else "")
                + " [AMBIGUOUS — stub missing, do not reference]"
            )
        elif child.status in ("code", "ambiguous") and child.ocaml:
            parts.append(
                f"\n{child.id}" + (f" — {child.header}" if child.header else "")
            )
            parts.append(
                f"```<sub-provision-code>\n{child.ocaml}\n```</sub-provision-code>"
            )
        else:
            parts.append("\n" + _child_text(child))

    if node.continuation:
        parts.append(node.continuation)

    if node.is_leaf:
        parts.append(
            f"\nThis is a terminal provision (no sub-provisions). "
            f"Write OCaml for {node.id}: a type/let binding if it defines a term "
            f"(pattern 'definition'), a comment stub if it is a clause fragment that "
            f"completes at the containing provision level (pattern 'partial')."
        )
    else:
        parts.append(f"\nWrite an OCaml function for provision {node.id}.")
    return "\n".join(parts)


def call_agent(node, results, context=None, type_preamble=None, all_ids=None):
    user_message = build_user_message(node, context, type_preamble)
    base_prompt = SYSTEM_PROMPT + "\n\n---\n\n" + user_message

    print(f"[agent] {node.id} — {node.header}", file=sys.stderr)

    full_prompt = base_prompt
    for attempt in range(3):
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

        if all_ids and node.ocaml:
            ok, issues = _run_checker(node, node.ocaml, all_ids)
            if not ok:
                print(
                    f"  [checker] attempt {attempt + 1} FAIL: {issues}", file=sys.stderr
                )
                if attempt < 2:
                    full_prompt = base_prompt + (
                        f"\n\n---\n\nPrevious attempt was rejected by the code reviewer.\n"
                        f"Issues found:\n{issues}\n\nFix these issues and return corrected JSON."
                    )
                    continue
                else:
                    print(
                        "  [checker] max retries reached, keeping last output",
                        file=sys.stderr,
                    )
            else:
                if attempt > 0:
                    print(
                        f"  [checker] passed on attempt {attempt + 1}", file=sys.stderr
                    )
        break
    node.status = (
        "ambiguous"
        if node.pattern == "ambiguous"
        else ("partial" if node.pattern == "partial" else "code")
        # "definition" counts as "code" — added to formalized and usable as context
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


# ── Type generation pass ───────────────────────────────────────────────────────


def build_type_index(types_ml_source):
    """
    Strip OCaml comments from types.ml and return compact type declarations only.
    Removes (* ... *) comments so the agent gets names/constructors without docs.
    """
    # Remove (* ... *) comments (non-greedy, handles multiline)
    stripped = re.sub(r"\(\*.*?\*\)", "", types_ml_source, flags=re.DOTALL)
    # Collapse blank lines
    lines = [ln for ln in stripped.splitlines() if ln.strip()]
    return "\n".join(lines)


def generate_types(tree, tags=None, out_path="data/types.ml"):
    """
    Pass 1: one agent call generates all OCaml types from definition leaves only.
    Saves result to out_path and returns the type source as a string.
    """
    if tags is None:
        tags = {}
    parts = ["Definition provisions of 26 USC § 7701:\n"]
    for node in tree.walk():
        if node.is_leaf and "definition" in tags.get(node.id, set()):
            label = node.id + (f" — {node.header}" if node.header else "")
            text = node.raw_text()
            if text:
                parts.append(f"\n{label}\n{text}")

    user_message = (
        "\n".join(parts) + "\n\nGenerate the shared OCaml types for these definitions."
    )
    full_prompt = TYPE_SYSTEM_PROMPT + "\n\n---\n\n" + user_message

    print("[type-pass] generating shared types...", file=sys.stderr)
    result = subprocess.run(
        ["claude", "-p", full_prompt, "--model", "claude-sonnet-5"],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[:300]}", file=sys.stderr)
        return ""

    raw = result.stdout.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0].strip()

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(raw + "\n")
    print(f"  wrote {out_path}", file=sys.stderr)
    return raw


# ── Classify tags ──────────────────────────────────────────────────────────────


def load_classify_tags():
    """
    Load the latest classify_rules JSON from logs/.
    Returns {node_id: set of construct strings}, empty dict if none found.
    """
    import glob

    files = sorted(glob.glob(os.path.join(_CLASSIFY_LOG_DIR, "classify_rules_*.json")))
    if not files:
        return {}
    with open(files[-1], encoding="utf-8") as f:
        data = json.load(f)
    return {
        r["id"]: {t["construct"] for t in r.get("tags", [])}
        for r in data.get("results", [])
    }


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", help="Process single subtree by node ID")
    parser.add_argument(
        "--gen-types",
        action="store_true",
        help="Generate shared types only (writes types.ml) and exit",
    )
    args = parser.parse_args()

    tree = Tree(TREE_FILE)
    total = sum(1 for _ in tree.walk())
    print(f"Loaded: {tree.root.id}, {total} nodes", file=sys.stderr)

    tags = load_classify_tags()
    print(f"Loaded classify tags for {len(tags)} nodes", file=sys.stderr)

    if args.gen_types:
        generate_types(tree, tags)
        return

    if os.path.exists("data/types.ml"):
        with open("data/types.ml", encoding="utf-8") as f:
            type_preamble = build_type_index(f.read())
        print("Loaded data/types.ml (compact index)", file=sys.stderr)
    else:
        print("WARNING: data/types.ml not found — run --gen-types first", file=sys.stderr)
        type_preamble = ""

    deps = build_dep_graph(tree)
    node_by_id = {n.id: n for n in tree.walk()}
    depth_map = {n.id: len(n.id.split("(")) - 1 for n in tree.walk()}
    order = topo_sort(deps, depth_map)

    results = []
    ts = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    out_json = f"logs/formalize/formalize_ocaml_{ts}.json"

    if args.node:
        target = tree.find(args.node)
        if not target:
            print(f"Node {args.node} not found", file=sys.stderr)
            sys.exit(1)
        subtree_ids = {n.id for n in tree.walk(target)}
        filtered = [node_by_id[nid] for nid in order if nid in subtree_ids]
        process_flat(filtered, deps, results, tags, type_preamble)
        for nid in order:
            if nid in subtree_ids:
                n = node_by_id[nid]
                if n.ocaml:
                    print(n.ocaml)
                    print()
    else:
        out_ml = "data/7701.ml"
        process_flat(
            [node_by_id[nid] for nid in order], deps, results, tags, type_preamble
        )

        with open(out_ml, "w", encoding="utf-8") as f:
            if type_preamble:
                f.write("(* shared types *)\n" + type_preamble + "\n\n")
            for nid in order:
                n = node_by_id[nid]
                if n.ocaml:
                    f.write(n.ocaml + "\n\n")
        print(f"Wrote {out_ml}", file=sys.stderr)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_json}", file=sys.stderr)


if __name__ == "__main__":
    main()
