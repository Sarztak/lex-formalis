"""
Structural validation of a scraped IRC section tree.

Assumptions being validated:
  - Chapeau signals further subdivision: a node with a chapeau always has children,
    and a node with children always has a chapeau (not body).
  - Body is terminal text: only leaf nodes carry body, and body never ends with
    em dash or colon (those are split signals belonging to chapeau).
  - Chapeau always ends with em dash or colon to signal the split into children.
  - A node with only a header and no body, chapeau, or children is anomalous —
    in practice these are repealed sections that Cornell LII renders as a bare title.
    A header-only node WITH children is valid: the header labels the group and
    content lives entirely in the children (e.g. 7701(a)(36)).

Known findings from §7701:
  - 7701(a)(33)(A)(iii): leaf whose body ends with em dash — em dash is content,
    not a split signal; false positive for check 5.
  - 7701(p)(1): leaf whose body ends with colon — colon introduces a list that
    was not scraped as subsection divs; also a duplicate node id (scraping bug).
  - 7701(a)(34), 7701(a)(47): header-only nodes — both are repealed sections.

Checks:
  1. Chapeau exists but node has no children
  2. Body exists but node has children
  3. Both chapeau and body exist on the same node
  4. Chapeau exists but does not end with em dash or colon
  5. Body ends with em dash or colon
  6. Header only — no chapeau, body, or children (likely repealed)

Usage:
    python scripts/validate_tree.py 101
    python scripts/validate_tree.py 101 7701
"""

import argparse
import json
import os
import sys


def load_tree(section):
    path = f"data/{section}_tree.json"
    if not os.path.exists(path):
        sys.exit(f"Tree not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def walk(node):
    yield node
    for child in node.get("children", []):
        yield from walk(child)


def validate(tree):
    findings = []

    for node in walk(tree):
        nid = node["id"]
        chapeau = node.get("chapeau", "").strip()
        body = node.get("body", "").strip()
        children = node.get("children", [])

        if chapeau and not children:
            findings.append((nid, "chapeau but no children"))

        if body and children:
            findings.append((nid, "body but has children"))

        if chapeau and body:
            findings.append((nid, "both chapeau and body"))

        if chapeau and not chapeau.endswith(("—", ":")):
            findings.append((nid, f"chapeau does not end with em dash or colon: ...{chapeau[-30:]}"))

        if body and body.endswith(("—", ":")):
            findings.append((nid, f"body ends with em dash or colon: ...{body[-30:]}"))

        if node.get("header", "").strip() and not chapeau and not body and not children:
            findings.append((nid, "header only — no chapeau, body, or children"))

    return findings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sections", nargs="+")
    args = parser.parse_args()

    for section in args.sections:
        tree = load_tree(section)
        findings = validate(tree)
        print(f"§{section}: {len(findings)} finding(s)")
        for nid, msg in findings:
            print(f"  {nid}: {msg}")


if __name__ == "__main__":
    main()
