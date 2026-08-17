"""
For each phrase in 7701_exception_phrases.json, find which nodes contain it,
then ask Claude whether the phrase in that node context is a genuine exception
(overrides/qualifies/carves-out from a prior provision) or a false positive.

Batches all matching phrases per node into one LLM call.
Output: logs/exceptions/7701_phrase_eval.json + printed report.

Usage:
    python scripts/eval_exception_phrases.py 7701
"""

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from statute import load_lookup, build_child_map  # type: ignore

LOG_DIR = "logs/exceptions"
MODEL = "claude-sonnet-4-6"

SYSTEM = (
    "You are an expert tax attorney with deep knowledge of the Internal Revenue Code (IRC). "
    "You reason carefully about statutory structure."
)

TASK = """\
Below is the text of an IRC provision and a list of phrases found in it.
For each phrase, determine whether it is being used as a genuine exception —
language that overrides, limits, qualifies, or carves out from a prior provision —
or whether it is a false positive (used in a definition, computation formula,
condition for applicability, cross-reference, or any other non-exception sense).

Return a JSON array, one object per phrase, in the same order as given:
[
  {"phrase": "...", "verdict": "exception" | "false_positive", "reason": "one line"}
]
"""


def node_flat_text(node):
    """Text fields of the node itself only (no children)."""
    parts = []
    for field in ("header", "chapeau", "body", "merged_body", "continuation"):
        if t := node.get(field, "").strip():
            parts.append(t)
    return " ".join(parts)


def run_eval(node_id, node_text_str, phrases):
    payload = json.dumps({
        "node_id": node_id,
        "node_text": node_text_str,
        "phrases": phrases,
    }, indent=2, ensure_ascii=False)
    prompt = SYSTEM + "\n\n" + TASK + "\n\n" + payload
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", MODEL],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None, result.stderr[:300]
    raw = result.stdout.strip()
    # strip markdown fences
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0].strip()
    # extract first JSON array
    start = raw.find("[")
    end = raw.rfind("]")
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

    phrases_path = os.path.join(LOG_DIR, f"{args.section}_exception_phrases.json")
    if not os.path.exists(phrases_path):
        sys.exit(f"Missing {phrases_path} — run scan_exceptions.py {args.section} first")

    with open(phrases_path, encoding="utf-8") as f:
        phrases = json.load(f)

    lookup = load_lookup(args.section)

    # For each node, collect which phrases appear in its flat text
    node_phrase_map = defaultdict(list)
    for node in lookup.values():
        text = node_flat_text(node).lower()
        for phrase in phrases:
            if phrase.lower() in text:
                node_phrase_map[node["id"]].append(phrase)

    total_pairs = sum(len(v) for v in node_phrase_map.values())
    print(f"{len(phrases)} phrases × {len(lookup)} nodes → {len(node_phrase_map)} nodes with matches, {total_pairs} (node, phrase) pairs", file=sys.stderr)

    # One LLM call per node
    tasks = []
    for node_id, matched_phrases in node_phrase_map.items():
        node = lookup[node_id]
        tasks.append((node_id, node_flat_text(node), matched_phrases))

    results_by_node = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_map = {
            executor.submit(run_eval, nid, text, ph): nid
            for nid, text, ph in tasks
        }
        for future in concurrent.futures.as_completed(future_map):
            nid = future_map[future]
            verdicts, error = future.result()
            if error:
                print(f"  [error] {nid}: {error}", file=sys.stderr)
            else:
                results_by_node[nid] = verdicts
                print(f"  [ok] {nid}: {len(verdicts)} phrases evaluated", file=sys.stderr)

    # Aggregate: for each phrase, collect all verdicts across nodes
    phrase_verdicts = defaultdict(list)  # phrase -> list of {node_id, verdict, reason}
    for nid, verdicts in results_by_node.items():
        if not verdicts:
            continue
        for v in verdicts:
            phrase_verdicts[v["phrase"]].append({
                "node_id": nid,
                "verdict": v["verdict"],
                "reason": v.get("reason", ""),
            })

    # Classify each phrase overall
    # true_exception: at least one node where it's a genuine exception
    # false_positive: all nodes say false_positive
    # not_found: phrase not matched in any node
    summary = []
    for phrase in phrases:
        entries = phrase_verdicts.get(phrase, [])
        if not entries:
            overall = "not_found"
        elif any(e["verdict"] == "exception" for e in entries):
            overall = "exception"
        else:
            overall = "false_positive"
        summary.append({"phrase": phrase, "overall": overall, "nodes": entries})

    os.makedirs(LOG_DIR, exist_ok=True)
    out_path = os.path.join(LOG_DIR, f"{args.section}_phrase_eval.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path}", file=sys.stderr)

    # Print report
    exceptions = [s for s in summary if s["overall"] == "exception"]
    false_positives = [s for s in summary if s["overall"] == "false_positive"]
    not_found = [s for s in summary if s["overall"] == "not_found"]

    print(f"\n=== RESULTS ===")
    print(f"  {len(exceptions)} genuine exceptions")
    print(f"  {len(false_positives)} false positives")
    print(f"  {len(not_found)} not found in any node")

    print(f"\n--- FALSE POSITIVES ({len(false_positives)}) ---")
    for s in false_positives:
        reason = s["nodes"][0]["reason"] if s["nodes"] else ""
        print(f"  [{s['nodes'][0]['node_id'] if s['nodes'] else '?'}] {s['phrase']!r}")
        if reason:
            print(f"      → {reason}")

    print(f"\n--- NOT FOUND ({len(not_found)}) ---")
    for s in not_found:
        print(f"  {s['phrase']!r}")


if __name__ == "__main__":
    main()
