"""
Post-processing pass on batch results.
Applies deterministic fixes and writes cleaned output files.

Fixes applied:
  1. Deduplicate signals by (type + primary key field)
  2. Drop EXTERNAL_DEPENDENCY with empty term (crossref nodes with headerless children)
"""

import json
import sys


def signal_key(s):
    t = s.get("type", "")
    if t == "EXTERNAL_DEPENDENCY":
        return (t, s.get("term", ""))
    if t in ("MISSING_INPUT", "OUTPUT_OVERRIDE", "INPUT_TRANSFORM"):
        return (t, s.get("variable", ""))
    if t == "OPEN_ENUMERATION":
        return (t, s.get("enumeration", ""))
    if t == "AMBIGUOUS":
        return (t, s.get("description", "")[:80])
    return (t, json.dumps(s, sort_keys=True))


def process_signals(signals):
    seen = set()
    out = []
    for s in signals:
        if s.get("type") == "EXTERNAL_DEPENDENCY" and not s.get("term", "").strip():
            continue
        k = signal_key(s)
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    return out


def process_file(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    stats = {"nodes": 0, "signals_before": 0, "signals_after": 0, "dropped_empty_term": 0}
    for node_id, result in data.items():
        before = result["signals"]
        after = process_signals(before)
        dropped_empty = sum(
            1 for s in before
            if s.get("type") == "EXTERNAL_DEPENDENCY" and not s.get("term", "").strip()
        )
        stats["nodes"] += 1
        stats["signals_before"] += len(before)
        stats["signals_after"] += len(after)
        stats["dropped_empty_term"] += dropped_empty
        result["signals"] = after

    out_path = path.replace(".json", "_clean.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"{path}")
    print(f"  nodes:           {stats['nodes']}")
    print(f"  signals before:  {stats['signals_before']}")
    print(f"  signals after:   {stats['signals_after']}")
    print(f"  deduped/dropped: {stats['signals_before'] - stats['signals_after']}")
    print(f"  empty term drop: {stats['dropped_empty_term']}")
    print(f"  wrote:           {out_path}")


if __name__ == "__main__":
    files = sys.argv[1:] or ["batch_results.json", "batch_results2.json"]
    for f in files:
        process_file(f)
        print()
