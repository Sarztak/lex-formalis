"""
Scan a section for exception-like phrases using Claude.

Splits the full section text into chunks of ~25k chars and runs each in parallel.
Output: unique phrases/keywords that signal exception-like language.

Usage:
    python scripts/scan_exceptions.py 7701
"""

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from statute import load_lookup, build_child_map, node_text  # type: ignore

LOG_DIR = "logs/exceptions"
MODEL = "claude-sonnet-4-6"
CHUNK_SIZE = 25_000

SYSTEM = (
    "You are an expert tax attorney with deep knowledge of the Internal Revenue Code (IRC). "
    "You reason carefully about statutory structure and interpret provisions with precision."
)

TASK = (
    "Below is a portion of an IRC section. "
    "Identify every phrase or keyword in this text that signals exception-like language — "
    "language that overrides, limits, qualifies, or carves out from another provision. "
    "Return a JSON array of strings — the exact phrases only, nothing else."
)


def chunk_text(text, size):
    return [text[i:i + size] for i in range(0, len(text), size)]


def run_chunk(chunk):
    prompt = SYSTEM + "\n\n" + TASK + "\n\n" + chunk
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", MODEL],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None, result.stderr[:300]
    raw = result.stdout.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw), None
    except json.JSONDecodeError:
        return None, f"parse error: {raw[:200]}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("section")
    args = parser.parse_args()

    lookup = load_lookup(args.section)
    child_map = build_child_map(lookup)
    _, text = node_text(args.section, lookup, child_map)

    chunks = chunk_text(text, CHUNK_SIZE)
    print(f"{len(text)} chars → {len(chunks)} chunks", file=sys.stderr)

    all_phrases = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(run_chunk, c) for c in chunks]
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            phrases, error = future.result()
            if error:
                print(f"  [chunk error] {error}", file=sys.stderr)
            else:
                print(f"  [chunk ok] {len(phrases)} phrases", file=sys.stderr)
                all_phrases.extend(phrases)

    unique_phrases = sorted(set(p.lower().strip() for p in all_phrases))

    os.makedirs(LOG_DIR, exist_ok=True)
    out_path = os.path.join(LOG_DIR, f"{args.section}_exception_phrases.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(unique_phrases, f, indent=2, ensure_ascii=False)

    print(f"{len(unique_phrases)} unique phrases", file=sys.stderr)
    print(f"Wrote {out_path}", file=sys.stderr)
    for p in unique_phrases:
        print(p)


if __name__ == "__main__":
    main()
