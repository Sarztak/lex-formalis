"""
Formalize § 7701 nodes into OCaml using pattern-based agent prompt.
Each non-leaf node becomes an OCaml function; pattern chosen by agent.
"""

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime

CLASSIFY_LOG = "logs/classify_rules_20260801_035408.json"
TREE_FILE = "7701_tree.json"

PROMPT_TMPL = """\
You are formalizing a provision of US tax law (26 USC § 7701) into OCaml.

Read the provision below and write an OCaml function that captures its logical structure.

{provision_text}

Choose the pattern that best fits and write the OCaml:

Pattern 1 — Boolean disjunction: any one sub-provision being true qualifies the entity.
Use when sub-provisions are alternative sufficient conditions (joined by "or", or any one being true makes the entity qualify).
  let is_regulated_public_utility (entity : entity) : bool =
    furnishes_electricity entity ||
    transports_gas_pipeline entity ||
    transports_gas_rail entity

Pattern 2 — Boolean conjunction: all sub-provisions must hold simultaneously.
Use when sub-provisions are cumulative requirements, all must be satisfied.
  let is_cooperative_bank (institution : institution) : bool =
    no_capital_stock institution &&
    organized_cooperatively institution

Pattern 3 — Conditional definition: same term defined differently depending on context.
Use when the provision defines the same term differently based on a condition.
  let meaning_of_delegate (ref_official : official) : delegate =
    if refers_to_secretary ref_official then secretary_delegate ref_official
    else subordinate_delegate ref_official

Pattern 4 — Arithmetic computation: provision specifies a formula producing a numeric value.
Use when sub-provisions define how to compute an amount, ratio, or threshold.
  let cost_ratio (foreign_cost : money) (total_cost : money) : decimal =
    foreign_cost /. total_cost

  let tax_amount (income : money) (rate : decimal) : money =
    income *. rate

Pattern 5 — Mixed computation: logical condition selects which computation applies.
Use when sub-provisions apply different formulas or thresholds based on entity category.
  let material_assistance_ratio (facility : facility) : decimal =
    if is_qualified_facility facility then cost_ratio_b facility
    else cost_ratio_c facility

Pattern 6 — Grouping wrapper: provision introduces independent sub-provisions with no computation of its own.
Use when the provision is a heading or container — it groups definitions that are each independently complete.
Write an OCaml module whose name comes from the provision header or term, containing placeholder comments for each sub-provision:
  module SectionName = struct
    (* sub-provision A: defined separately *)
    (* sub-provision B: defined separately *)
  end

Pattern 7 — Partial: provision defines a named quantity or filtered set that is only part of a larger computation defined at the parent level.
Use when the provision text ends with "divided by", "plus", "minus", or describes a sub-expression without specifying the full computation.
Do NOT invent a formula, struct, or fields. Write a comment placeholder only:
  (* total_direct_costs_of_prohibited_products : money
     — partial expression, computation completes at parent level *)

Rules:
- snake_case function names derived from the term being defined or the header
- Name inputs from the provision text (entity, institution, person, facility, etc.)
- Do not invent conditions, types, struct fields, or formulas not present in the provision text
- Sub-provisions become function calls named after their content
- Write only the OCaml skeleton — use descriptive placeholder names for sub-conditions
- Do not use training knowledge to resolve cross-referenced sections. If any sub-provision references another section of law to define its meaning, set pattern to "ambiguous", ocaml to "", and name the sections needed in the reason.
- For numeric comparisons involving ratios, percentages, or monetary amounts use OCaml float operators: <. >. <=. >=. +. -. *. /. — not integer operators < > + - * /
- If the formula or computation is unspecified or delegated elsewhere, set pattern to "ambiguous", ocaml to "", and explain in reason.

Return JSON only, no prose, no markdown fences:
{{"ocaml": "the ocaml code", "pattern": "disjunction|conjunction|conditional|arithmetic|mixed|wrapper|partial|ambiguous", "reason": "one sentence"}}
"""


def walk(node):
    yield node
    for c in node.get("children", []):
        yield from walk(c)


def provision_text(node):
    parts = []
    if node.get("header"):
        parts.append(node["header"])
    if node.get("chapeau"):
        parts.append(node["chapeau"])
    if node.get("body"):
        parts.append(node["body"])
    if node.get("continuation"):
        parts.append(node["continuation"])
    return " ".join(parts).strip()


def format_provision(node, children):
    text = provision_text(node)
    lines = [text] if text else []
    for c in children:
        sub = provision_text(c)
        if sub:
            lines.append(f"  - {sub}")
    return "\n".join(lines) or "(no text)"


def call_agent(header, chapeau, body, continuation, children):
    node = {
        "header": header,
        "chapeau": chapeau,
        "body": body,
        "continuation": continuation,
    }
    prompt = PROMPT_TMPL.format(provision_text=format_provision(node, children))
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", "claude-sonnet-5"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    raw = result.stdout.strip()
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
        return parsed, None
    except json.JSONDecodeError:
        return None, raw[:300]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", nargs="+", default=None)
    parser.add_argument("--file", default=None, help="file with one node ID per line")
    args = parser.parse_args()

    with open(TREE_FILE, encoding="utf-8") as f:
        tree_data = json.load(f)

    node_map = {n["id"]: n for n in walk(tree_data)}

    if args.nodes:
        targets = args.nodes
    elif args.file:
        with open(args.file, encoding="utf-8") as f:
            targets = [line.strip() for line in f if line.strip()]
    else:
        print("Specify --nodes or --file", file=sys.stderr)
        sys.exit(1)

    results = []
    for node_id in targets:
        node = node_map.get(node_id, {})
        parsed, error = call_agent(
            node.get("header", ""),
            node.get("chapeau", ""),
            node.get("body", ""),
            node.get("continuation", ""),
            node.get("children", []),
        )
        row = {
            "id": node_id,
            "result": parsed,
            "error": error,
        }
        results.append(row)
        if parsed:
            print(f"\n{'=' * 60}")
            print(f"  {node_id}  [{parsed.get('pattern', '?')}]")
            print(f"  {parsed.get('reason', '')}")
            print(f"{'-' * 60}")
            print(parsed.get("ocaml", ""))
        else:
            print(f"\n  {node_id}  ERROR: {error}")

    ts = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    out_path = f"logs/formalize_ocaml_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nWritten: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
