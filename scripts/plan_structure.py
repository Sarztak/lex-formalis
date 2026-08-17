"""
Run the planning agent on a container from the recursive structure.

Usage:
    python scripts/plan_structure.py 7701 "7701(a)(51)(D)(ii)"
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

LOG_DIR = "logs/planning"
PROMPT_PATH = "prompts/planning_agent.md"


def load_prompt():
    with open(PROMPT_PATH, encoding="utf-8") as f:
        return f.read()


def load_type_names(section):
    path = f"data/{section}_types.ml"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            src = f.read()
        names = re.findall(r"^type\s+(\w+)", src, re.MULTILINE)
        return names, path
    return None, None


def load_recursive_json(section):
    path = f"logs/flatten/recursive_{section}.json"
    if not os.path.exists(path):
        sys.exit(
            f"Recursive JSON not found: {path} — run show_flatten.py {section} first"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def format_entry(container):
    level = container["level"]
    path = container["path"]
    path_str = "  >  ".join(f"{nid}: {hdr}" for nid, hdr in path)
    lines = []
    lines.append(f"[L{level}]  {path_str}")
    lines.append("=" * 70)
    if chapeau := container.get("chapeau", "").strip():
        lines.append(f"  [chapeau] {chapeau}")
    if cont := container.get("continuation", "").strip():
        lines.append(f"  [continuation] {cont}")
    for c in container["children"]:
        clevel = c["level"]
        tag = f"[L{clevel}]" if clevel is not None else "[?]"
        lines.append(f"  {c['id']}  —  {tag}  {c['header']}")
        if clevel == 0 and c.get("body", "").strip():
            lines.append(f"    {c['body']}")
    return "\n".join(lines)


def collect_subtree(root_id, containers):
    """Collect root and all descendant containers in pre-order."""
    if root_id not in containers:
        return []
    root = containers[root_id]
    result = [root]
    for c in root["children"]:
        result.extend(collect_subtree(c["id"], containers))
    return result


def build_input(node_id, containers):
    subtree = collect_subtree(node_id, containers)
    if not subtree:
        sys.exit(f"Container {node_id!r} not found — check the ID or re-run show_flatten.py")
    return "\n\n".join(format_entry(c) for c in subtree)


def run_agent(prompt, input_text):
    full_prompt = prompt + "\n\n## Input\n\n" + input_text
    print("[planning-agent] calling claude...", file=sys.stderr)
    result = subprocess.run(
        ["claude", "-p", full_prompt, "--model", "claude-sonnet-5"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        sys.exit(f"Agent error: {result.stderr[:500]}")
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("section", help="IRC section number (e.g. 7701)")
    parser.add_argument("node_id", help='Container node ID (e.g. "7701(a)(51)(D)(ii)")')
    args = parser.parse_args()

    prompt = load_prompt()
    data = load_recursive_json(args.section)
    containers = data["containers"]

    type_names, types_path = load_type_names(args.section)
    if types_path:
        print(f"Loaded type names from {types_path}", file=sys.stderr)

    input_text = build_input(args.node_id, containers)
    if type_names:
        names_line = ", ".join(type_names)
        input_text = (
            "The following types are already declared for this section"
            " — reference them by name, do not redefine:\n"
            f"{names_line}\n\n---\n\n"
            + input_text
        )
    output = run_agent(prompt, input_text)

    os.makedirs(LOG_DIR, exist_ok=True)
    safe_id = args.node_id.replace("(", "_").replace(")", "").strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(LOG_DIR, f"{args.section}_{safe_id}_{timestamp}")

    with open(base + ".txt", "w", encoding="utf-8") as f:
        f.write(output)
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(
            {"section": args.section, "node_id": args.node_id, "input": input_text, "output": output},
            f, indent=2, ensure_ascii=False,
        )

    print(f"Wrote {base}.txt", file=sys.stderr)
    print(output)


if __name__ == "__main__":
    main()
