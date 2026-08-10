"""
Assemble a .ml file from a formalize_ocaml JSON log.
Log entries are already in topological order.

Usage:
    python pipeline/assemble_ml.py 101
    python pipeline/assemble_ml.py 101 --no-compile
    python pipeline/assemble_ml.py 101 --out data/my_101.ml
"""

import argparse
import json
import os
import subprocess
import sys


def load_log(section, log_override=None):
    path = log_override or f"logs/formalize/formalize_ocaml_{section}.json"
    if not os.path.exists(path):
        print(f"Log file not found: {path} — run formalize_ocaml.py {section} first", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f), path


def load_types(section, types_override=None):
    path = types_override or f"data/{section}_types.ml"
    if not os.path.exists(path):
        print(f"WARNING: {path} not found — omitting preamble", file=sys.stderr)
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def assemble(results, types_src, out_path):
    with open(out_path, "w", encoding="utf-8") as f:
        if types_src:
            f.write("(* shared types *)\n")
            f.write(types_src.rstrip())
            f.write("\n\n")

        written = 0
        for r in results:
            ocaml = r.get("ocaml", "") or ""
            if not ocaml.strip():
                continue
            node_id = r.get("id", "")
            status = r.get("status", "")
            # skip pure comment stubs from partial/repealed leaves — they add nothing
            if status in ("partial", "repealed"):
                continue
            f.write(f"(* {node_id} — {status} *)\n")
            f.write(ocaml.rstrip())
            f.write("\n\n")
            written += 1

    print(f"Wrote {written} OCaml blocks to {out_path}", file=sys.stderr)
    return out_path


def check_compile(ml_path):
    print(f"Compiling {ml_path} ...", file=sys.stderr)
    result = subprocess.run(
        ["ocaml", ml_path],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode == 0:
        print("OK — no compile errors", file=sys.stderr)
    else:
        print("ERRORS:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
    return result.returncode, result.stderr


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("section", help="IRC section number (e.g. 101)")
    parser.add_argument("--log", help="Override log file path")
    parser.add_argument("--out", help="Override output .ml file path")
    parser.add_argument("--types", help="Override shared types .ml file path")
    parser.add_argument("--no-compile", action="store_true", help="Skip compile check")
    args = parser.parse_args()

    results, log_path = load_log(args.section, args.log)
    print(f"Using log: {log_path}", file=sys.stderr)

    types_src = load_types(args.section, args.types)
    out_path = args.out or f"data/{args.section}_assembled.ml"

    assemble(results, types_src, out_path)

    if not args.no_compile:
        rc, _ = check_compile(out_path)
        sys.exit(rc)


if __name__ == "__main__":
    main()
