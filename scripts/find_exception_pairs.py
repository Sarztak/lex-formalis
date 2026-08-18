""" For each base-case "In general"/"General rule" node in the merged lookup,
call node_text on its parent to get the full flattened context, then ask
Claude to identify exception pairs: which node overrides/qualifies which.

Uses the merged lookup (logs/flatten/merged_{section}.json) throughout —
not the raw tree. Same approach as exception_context.py.

Output: logs/exceptions/{section}_exception_pairs_{timestamp}.json

Usage:
    python scripts/find_exception_pairs.py 7701
"""

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from statute import load_lookup, build_child_map, node_text, get_parent  # type: ignore

LOG_DIR = "logs/exceptions"
MODEL = "claude-sonnet-4-6"

EXC_PATTERN = re.compile(
    r"\bexception|limitation|special rule|notwithstanding|shall not\b|except as\b", re.I
)
DEFN_PATTERN = re.compile(r"the terms?\s|any term used\b", re.I)

SYSTEM = (
    "You are an expert tax attorney with deep knowledge of the Internal Revenue Code (IRC). "
    "You reason carefully about statutory structure and interpret provisions with precision."
)

TASK = (
    "Below is the text of an IRC provision structured as sibling nodes. "
    "Each provision A has the form (T_A, E_A) where T_A is the set of condition predicates "
    "and E_A is the set of effect predicates asserted when all conditions in T_A hold.\n\n"
    "Identify every pair where node B intervenes on node A. "
    "Only direct interventions — not downstream. "
    "Also identify exceptions to exceptions: if B intervenes on A and C intervenes on B, report both pairs.\n\n"
    "Classify each intervention as exactly one of three operations:\n\n"
    "  op: \"void_provision\"    ~A | C_B     A is not consulted at all when C_B holds\n"
    "  op: \"void_conclusion\"   ~E_A | C_B   T_A is evaluated but no effect in E_A is asserted when C_B holds\n"
    "  op: \"subst\"             A[f ↦ f']   a predicate f in T_A or E_A is replaced by f'\n\n"
    "For subst, provide:\n"
    "  f        -- short predicate name (e.g. days_present, united_states, employee)\n"
    "  f_domain -- \"T\" if f is a condition predicate, \"E\" if f is an effect predicate\n"
    "  f_prime  -- the formula for what f becomes, using one of:\n"
    "               ~f       negation\n"
    "               f'       disjoint replacement -- write the new predicate name\n"
    "               f ∩ X    narrowing  -- describe X\n"
    "               f ∪ X    broadening -- describe X\n"
    "               ⊥        elimination (E only)\n\n"
    "Return a JSON array only:\n"
    '[{"overriding": "node_id", "overridden": "node_id", "op": "...", '
    '"f": "predicate (subst only)", "f_domain": "T or E (subst only)", '
    '"f_prime": "formula (subst only)", "reasoning": "one line"}]'
)


def is_base_case(node, lookup):
    """Node must have In general/General rule header, no exception language in own text, no definition language, and no exception keyword in any ancestor header."""
    own_text = " ".join(node.get(f, "") for f in ("chapeau", "body", "merged_body", "continuation"))
    if DEFN_PATTERN.search(own_text) or EXC_PATTERN.search(own_text):
        return False
    nid = node["id"]
    while True:
        try:
            parent = get_parent(nid, lookup)
        except KeyError:
            break
        if EXC_PATTERN.search(parent.get("header", "")):
            return False
        nid = parent["id"]
    return True


def run_llm(parent_id, text):
    prompt = "\n\n".join([SYSTEM, TASK, f"Node id: {parent_id}\n\n{text}"])
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", MODEL],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None, result.stderr[:300]
    raw = result.stdout.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0].strip()
    start, end = raw.find("["), raw.rfind("]")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    try:
        return json.loads(raw), None
    except json.JSONDecodeError:
        return None, f"parse error: {raw[:200]}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("section", default="7701", nargs="?")
    args = parser.parse_args()

    lookup = load_lookup(args.section)
    child_map = build_child_map(lookup)

    # Collect candidate parent IDs from base-case In general / General rule nodes.
    # Sorted traversal guarantees ancestors appear before descendants.
    # After collection, drop any candidate whose ancestor is also a candidate —
    # the ancestor's context already contains the descendant's pairs.
    candidate_parents: set[str] = set()
    for node in sorted(lookup.values(), key=lambda n: n["id"]):
        if node.get("header", "").strip().lower() not in ("in general", "general rule"):
            continue
        if not is_base_case(node, lookup):
            continue
        try:
            parent = get_parent(node["id"], lookup)
        except KeyError:
            print(f"  [skip] {node['id']}: no parent in lookup", file=sys.stderr)
            continue
        candidate_parents.add(parent["id"])

    # Keep only the highest ancestor in each lineage.
    tasks = []
    for pid in sorted(candidate_parents):
        if any(pid.startswith(ancestor + "(") for ancestor in candidate_parents if ancestor != pid):
            continue
        try:
            _, text = node_text(pid, lookup, child_map)
            tasks.append((pid, text))
        except KeyError as e:
            print(f"  [skip] {pid}: {e}", file=sys.stderr)

    print(f"{len(tasks)} unique parents to evaluate", file=sys.stderr)

    all_pairs = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_map = {executor.submit(run_llm, pid, text): pid for pid, text in tasks}
        for future in concurrent.futures.as_completed(future_map):
            pid = future_map[future]
            pairs, error = future.result()
            if error:
                print(f"  [error] {pid}: {error}", file=sys.stderr)
            else:
                pairs = pairs or []
                print(f"  [ok] {pid}: {len(pairs)} pairs", file=sys.stderr)
                for p in pairs:
                    p["context_parent"] = pid
                all_pairs.extend(pairs)

    all_pairs.sort(key=lambda p: (p.get("context_parent", ""), p.get("overriding", "")))

    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(LOG_DIR, f"{args.section}_exception_pairs_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_pairs, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path} — {len(all_pairs)} pairs total", file=sys.stderr)

    for p in all_pairs:
        op = p.get("op", "?")
        subst = f"  [{p['f']} -> {p['f_prime']}]" if op == "subst" else ""
        print(f"  {p['overriding']} → {p['overridden']}  {op}{subst}  {p.get('reasoning','')}")


if __name__ == "__main__":
    main()
