"""
Resolve cross-references in any scraped IRC section tree.

Two component types in CHAIN_RE:
  _COMP     — paragraph/subparagraph/clause/etc. + stacked paren designators
  _SEC_COMP — section + bare digit-starting number (optionally followed by paren designators)

CHAIN_RE matches the full reference in one shot:
  first component + optional bare followons + optional outer anchors (via _OF)

Section refs are always MISSING (external to the parsed section); caller can filter by "section" kw later.

Usage:
    python pipeline/resolve_refs.py 7701
    python pipeline/resolve_refs.py 101

Output: logs/resolve/resolve_refs_{section}.txt (overwrites)
"""

import argparse
import json
import os
import re

LOG_DIR = "logs/resolve"

LEVEL = {
    "section": 0,  # caught for completeness; always external / MISSING
    "subsection": 1,
    "paragraph": 2,
    "subparagraph": 3,
    "clause": 4,
    "subclause": 5,
    "item": 6,
    "subitem": 7,
}

_KW_INNER = (
    r"(?:paragraphs?|subparagraphs?|clauses?|subclauses?|items?|subitems?|subsections?)"
)
_DESIG = r"(?:\([^)]+\))+"  # stacked paren designators: (A)(i)(I)...
_COMP = rf"(?:{_KW_INNER})\s*{_DESIG}"

_KW_SEC = r"sections?"
_SEC_DESIG = (
    r"\s+\d\w*(?:\([^)]+\))*"  # " 1441" or " 408(a)(1)(B)" — must start with digit
)
_SEC_COMP = rf"(?:{_KW_SEC}){_SEC_DESIG}"

_ANY_COMP = rf"(?:{_COMP}|{_SEC_COMP})"

# One bare followon: ", (ii)", "or (iii)", ", or (iv)", "through (F)"
_BARE = r"(?:\s*(?:,\s*(?:(?:and|or)\s+)?|(?:and|or|through)\s+)\([^)]+\))"
# Chain connector: "of" or "of such"
_OF = r"\s+of(?:\s+such)?\s+"

# Full pattern: first component + optional followons + optional outer anchors
CHAIN_RE = re.compile(
    rf"(?:{_ANY_COMP}){_BARE}*(?:{_OF}(?:{_ANY_COMP}){_BARE}*)*",
    re.IGNORECASE,
)

COMP_RE = re.compile(rf"({_KW_INNER})\s*((?:\([^)]+\))+)", re.IGNORECASE)
SEC_COMP_RE = re.compile(rf"({_KW_SEC})\s+(\d\w*)((?:\([^)]+\))*)", re.IGNORECASE)

NUM_RE = re.compile(r"\(([^)]+)\)")
VALID_NUM = re.compile(r"^[a-zA-Z0-9]+$")


def normalize_kw(kw):
    """Strip plural 's' to singular form used in LEVEL."""
    kw = kw.lower()
    if kw.endswith("s") and kw[:-1] in LEVEL:
        return kw[:-1]
    return kw


def parse_id(node_id):
    """'7701(a)(31)(B)' → ['7701', '(a)', '(31)', '(B)']"""
    m = re.match(r"^\d+", node_id)
    if not m:
        raise ValueError(f"node_id has no leading section number: {node_id!r}")
    return [m.group(0)] + re.findall(r"\([^)]+\)", node_id)


def resolve_chain(current_parts, components):
    """
    Build target ID from sorted components (outermost first).
    prefix = current_parts[:outermost_level]; append all nums in order.
    """
    if not components:
        return None
    outermost_level = LEVEL.get(components[0][0])
    if outermost_level is None:
        return None
    prefix = current_parts[:outermost_level]
    all_nums = [n for _, nums in components for n in nums]
    return "".join(prefix + [f"({n})" for n in all_nums])


def extract_components(match_text):
    """
    Return (raw_components, comp_spans) from a CHAIN_RE match.
    raw_components: [(kw, [num, ...]), ...]  unsorted
    comp_spans:     [(start, end), ...]      parallel list
    """
    raw = []
    spans = []

    for cm in COMP_RE.finditer(match_text):
        kw = normalize_kw(cm.group(1))
        if kw not in LEVEL:
            continue
        nums = [n for n in NUM_RE.findall(cm.group(2)) if VALID_NUM.match(n)]
        raw.append((kw, nums))
        spans.append((cm.start(), cm.end()))

    for cm in SEC_COMP_RE.finditer(match_text):
        if any(s <= cm.start() < e for s, e in spans):
            continue
        bare = cm.group(2)
        paren_nums = [n for n in NUM_RE.findall(cm.group(3)) if VALID_NUM.match(n)]
        raw.append(("section", [bare] + paren_nums))
        spans.append((cm.start(), cm.end()))

    return raw, spans


def find_refs(node_id, text):
    """Find all resolved reference IDs in text. Returns list of (label, target_id)."""
    parts = parse_id(node_id)
    results = []

    for m in CHAIN_RE.finditer(text):
        match_text = m.group(0)

        raw_components, comp_spans = extract_components(match_text)
        if not raw_components:
            continue

        # Bare (num) not inside any component span = followon nums for innermost keyword
        followon_nums = [
            nm.group(1)
            for nm in NUM_RE.finditer(match_text)
            if VALID_NUM.match(nm.group(1))
            and not any(s <= nm.start() < e for s, e in comp_spans)
        ]

        # Sort outermost-first by level
        all_components = sorted(raw_components, key=lambda x: LEVEL.get(x[0], 99))

        target = resolve_chain(parts, all_components)
        if target:
            results.append((match_text, target))

        # Followons replace the INNERMOST (deepest, last) component's num
        if followon_nums:
            innermost_kw = all_components[-1][0]
            outer = all_components[:-1]
            for extra_num in followon_nums:
                extra = sorted(
                    outer + [(innermost_kw, [extra_num])],
                    key=lambda x: LEVEL.get(x[0], 99),
                )
                extra_target = resolve_chain(parts, extra)
                if extra_target:
                    results.append((f"(follow-on) ({extra_num})", extra_target))

    return results


def walk(node):
    yield node
    for c in node.get("children", []):
        yield from walk(c)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("section", help="IRC section number (e.g. 101)")
    args = parser.parse_args()

    tree_path = f"data/{args.section}_tree.json"
    if not os.path.exists(tree_path):
        parser.error(f"Tree file not found: {tree_path} — run parse_section.py {args.section} first")

    with open(tree_path, encoding="utf-8") as f:
        data = json.load(f)

    all_ids = {node["id"] for node in walk(data)}

    lines = []
    for node in walk(data):
        node_id = node["id"]
        for field in ("header", "chapeau", "body", "continuation"):
            text = node.get(field) or ""
            if not text:
                continue
            for label, target in find_refs(node_id, text):
                status = "OK" if target in all_ids else "MISSING"
                lines.append(f'[{node_id}] [{field}] "{label}" → {target} [{status}]')

    os.makedirs(LOG_DIR, exist_ok=True)
    out_path = os.path.join(LOG_DIR, f"resolve_refs_{args.section}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    ok = sum(1 for ln in lines if "[OK]" in ln)
    missing = sum(1 for ln in lines if "[MISSING]" in ln)
    print(f"{len(lines)} refs: {ok} resolved OK, {missing} MISSING → {out_path}")


if __name__ == "__main__":
    main()
