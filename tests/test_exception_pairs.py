"""
Mixed positive/negative tests for find_exception_pairs LLM prompt.

Positive: parents with confirmed exception pairs — model must find at least the known pairs.
Negative (no In general): parents with In general but no exception siblings — model must return [].
Negative (no In general, definition nodes): randomly picked definition nodes — model must return [].

Usage:
    python tests/test_exception_pairs.py
"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from statute import load_lookup, build_child_map, node_text  # type: ignore
from find_exception_pairs import run_llm  # type: ignore

SECTION = "7701"

# Known pairs that must appear in positive test output: (overriding, overridden)
POSITIVE_CASES = {
    "7701(b)(3)": [
        ("7701(b)(3)(B)", "7701(b)(3)(A)"),
        ("7701(b)(3)(C)", "7701(b)(3)(B)"),
        ("7701(b)(3)(D)", "7701(b)(3)(A)"),
    ],
    "7701(b)(7)": [
        ("7701(b)(7)(B)", "7701(b)(7)(A)"),
        ("7701(b)(7)(C)", "7701(b)(7)(A)"),
        ("7701(b)(7)(D)", "7701(b)(7)(A)"),
    ],
    "7701(e)": [
        ("7701(e)(3)(A)",    "7701(e)(1)"),
        ("7701(e)(3)(A)",    "7701(e)(2)"),
        ("7701(e)(4)(A)",    "7701(e)(3)(A)"),
        ("7701(e)(4)(B)",    "7701(e)(4)(A)"),
        ("7701(e)(4)(C)(i)", "7701(e)(4)(A)"),
        ("7701(e)(4)(C)(ii)","7701(e)(4)(A)"),
        ("7701(e)(5)",       "7701(e)(1)"),
        ("7701(e)(5)",       "7701(e)(2)"),
        ("7701(e)(5)",       "7701(e)(3)(A)"),
    ],
}

# Parents with In general but no exception siblings — should return []
NEGATIVE_NO_EXCEPTION = [
    "7701(b)(9)",   # In general: defines when days don't count for aliens — no sibling exceptions
]

# Pure definition nodes with no In general at all — should return []
NEGATIVE_DEFINITIONS = [
    "7701(a)(1)",   # 'Person' definition
    "7701(a)(3)",   # 'Corporation' definition
    "7701(a)(9)",   # 'United States' definition
]

def get_text(parent_id, lookup, child_map):
    _, text = node_text(parent_id, lookup, child_map)
    return text

def found_pair(pairs, overriding, overridden):
    return any(
        p.get("overriding") == overriding and p.get("overridden") == overridden
        for p in (pairs or [])
    )

def run_test(label, parent_id, text, expected_pairs: list | None = None, expect_empty=False):
    pairs, error = run_llm(parent_id, text)
    result = {"label": label, "parent_id": parent_id}
    if error:
        result["status"] = "ERROR"
        result["detail"] = error
        return result

    pairs = pairs or []
    if expect_empty:
        if pairs:
            result["status"] = "FAIL"
            result["detail"] = f"Expected [] but got {len(pairs)} pairs: {[(p.get('overriding'), p.get('overridden')) for p in pairs]}"
        else:
            result["status"] = "PASS"
            result["detail"] = "Correctly returned []"
    else:
        expected = expected_pairs or []
        missing = [(a, b) for a, b in expected if not found_pair(pairs, a, b)]
        if missing:
            result["status"] = "FAIL"
            result["detail"] = f"Missing pairs: {missing}. Got: {[(p.get('overriding'), p.get('overridden')) for p in pairs]}"
        else:
            result["status"] = "PASS"
            result["detail"] = f"Found all {len(expected)} expected pairs"

    result["pairs"] = pairs
    return result

def main():
    lookup = load_lookup(SECTION)
    child_map = build_child_map(lookup)

    tasks = []

    for parent_id, expected in POSITIVE_CASES.items():
        try:
            text = get_text(parent_id, lookup, child_map)
            tasks.append(("POSITIVE", parent_id, text, expected, False))
        except KeyError as e:
            print(f"[skip] {parent_id}: {e}")

    for parent_id in NEGATIVE_NO_EXCEPTION:
        try:
            text = get_text(parent_id, lookup, child_map)
            tasks.append(("NEG_NO_EXC", parent_id, text, None, True))
        except KeyError as e:
            print(f"[skip] {parent_id}: {e}")

    for parent_id in NEGATIVE_DEFINITIONS:
        try:
            text = get_text(parent_id, lookup, child_map)
            tasks.append(("NEG_DEF", parent_id, text, None, True))
        except KeyError as e:
            print(f"[skip] {parent_id}: {e}")

    results = []
    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(run_test, label, pid, text, exp, emp): pid
            for label, pid, text, exp, emp in tasks
        }
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda r: (r["parent_id"]))

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")

    print(f"\n{'='*70}")
    for r in results:
        icon = "✓" if r["status"] == "PASS" else "✗"
        print(f"  {icon} [{r['label']:<12}] {r['parent_id']:<35} {r['detail']}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(os.path.dirname(__file__), "..", "logs", "exceptions", f"test_exception_pairs_{ts}.json")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nLog: {log_path}")

    print(f"{passed} passed, {failed} failed, {errors} errors")
    if failed or errors:
        sys.exit(1)

if __name__ == "__main__":
    main()
