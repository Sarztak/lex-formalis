"""
Assemble a .ml file from a formalize_ocaml JSON log.
Log entries are already in topological order.
"""

import argparse
import glob
import json
import os
import subprocess
import sys

LOG_DIR = "logs/formalize"


def latest_log():
    files = sorted(glob.glob(os.path.join(LOG_DIR, "formalize_ocaml_*.json")))
    if not files:
        print("No formalize_ocaml_*.json logs found", file=sys.stderr)
        sys.exit(1)
    return files[-1]


def load_types(types_path="data/types.ml"):
    if not os.path.exists(types_path):
        print(f"WARNING: {types_path} not found — omitting preamble", file=sys.stderr)
        return ""
    with open(types_path, encoding="utf-8") as f:
        return f.read()


def assemble(log_path, out_path, types_path="data/types.ml"):
    with open(log_path, encoding="utf-8") as f:
        results = json.load(f)

    types_src = load_types(types_path)

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
    parser.add_argument("--log", help="JSON log file (default: latest)")
    parser.add_argument("--out", default="data/7701_assembled.ml", help="Output .ml file")
    parser.add_argument("--types", default="data/types.ml", help="Shared types .ml file")
    parser.add_argument(
        "--no-compile", action="store_true", help="Skip compile check"
    )
    args = parser.parse_args()

    log_path = args.log or latest_log()
    print(f"Using log: {log_path}", file=sys.stderr)

    out_path = assemble(log_path, args.out, args.types)

    if not args.no_compile:
        rc, _ = check_compile(out_path)
        sys.exit(rc)


if __name__ == "__main__":
    main()
