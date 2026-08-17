"""
Human-readable exception pattern analysis from logs/exception_corpus.json.

Groups exception nodes by signal type and shows full text for pattern review.
Goal: identify what kinds of exception edges actually appear in the IRC,
beyond what classify_rules.py currently captures.

Usage:
    python scripts/analyze_exceptions.py
    python scripts/analyze_exceptions.py --section 163
    python scripts/analyze_exceptions.py --signal "body: 'notwithstanding'"
"""

import argparse
import json
import os
from collections import defaultdict

CORPUS_FILE = "logs/exception_corpus.json"
OUT_FILE = "logs/exception_patterns.txt"

# Known signals from classify_rules.py — used to label groups in output
SIGNAL_LABELS = {
    "header contains 'Exception(s)' or 'Special rule(s)'": "HEADER_KEYWORD",
    "chapeau contains 'Exception(s)'": "CHAPEAU_KEYWORD",
    "body: 'shall not be treated as'": "BODY_EXCLUSION",
    "body: 'notwithstanding'": "BODY_NOTWITHSTANDING",
}


def node_text(node: dict) -> str:
    parts = []
    if node.get("chapeau"):
        parts.append(f"  chapeau: {node['chapeau']}")
    if node.get("body"):
        parts.append(f"  body:    {node['body']}")
    if node.get("continuation"):
        parts.append(f"  cont:    {node['continuation']}")
    return "\n".join(parts) if parts else "  (no text)"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", help="Filter to one section (e.g. 163)")
    parser.add_argument("--signal", help="Filter to nodes matching this signal substring")
    parser.add_argument("--out", default=OUT_FILE)
    args = parser.parse_args()

    with open(CORPUS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    nodes = data["nodes"]

    if args.section:
        nodes = [n for n in nodes if n["section"] == args.section]
    if args.signal:
        nodes = [n for n in nodes if any(args.signal in t["signal"] for t in n["tags"])]

    # Group by signal
    by_signal: dict[str, list] = defaultdict(list)
    for node in nodes:
        for tag in node["tags"]:
            if tag["construct"] == "exception":
                by_signal[tag["signal"]].append(node)

    lines = []
    lines.append("=" * 80)
    lines.append("IRC EXCEPTION PATTERN CORPUS")
    lines.append(f"Sections: {data['section_stats'].keys()}")
    lines.append(f"Total exception nodes: {data['total_exception_nodes']}")
    if args.section:
        lines.append(f"Filtered to: §{args.section}")
    lines.append("=" * 80)

    # Section stats table
    lines.append("\nPER-SECTION EXCEPTION COUNT:")
    for sec, stats in sorted(data["section_stats"].items(), key=lambda x: x[0].zfill(6)):
        ex = stats["exception_nodes"]
        total = stats["total_nodes"]
        pct = 100 * ex / total if total else 0
        lines.append(f"  §{sec:<6} {ex:>3} exception / {total:>4} total ({pct:.0f}%)")

    # Signal frequency table
    lines.append("\nSIGNAL FREQUENCY:")
    for sig, sig_nodes in sorted(by_signal.items(), key=lambda x: -len(x[1])):
        label = SIGNAL_LABELS.get(sig, sig)
        lines.append(f"  {len(sig_nodes):>3}  {label}")

    # Full text per signal group
    for sig, sig_nodes in sorted(by_signal.items(), key=lambda x: -len(x[1])):
        label = SIGNAL_LABELS.get(sig, sig)
        lines.append(f"\n{'=' * 70}")
        lines.append(f"SIGNAL: {label}  ({len(sig_nodes)} nodes)")
        lines.append("=" * 70)

        for node in sig_nodes:
            lines.append(f"\n  [{node['section']}] {node['id']}  header={node['header']!r}  children={node['child_count']}")
            lines.append(node_text(node))
            # Show all tags on this node (not just exception ones)
            all_tags = ", ".join(t["construct"] for t in node["tags"])
            lines.append(f"  tags: [{all_tags}]")

    output = "\n".join(lines)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(output + "\n")

    print(output)
    print(f"\n→ {args.out}")


if __name__ == "__main__":
    main()
