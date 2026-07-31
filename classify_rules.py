"""
Rule-based construct classifier for § 7701 nodes.
Bottom-up recursive walk: children classified before parent.
Parent construct determined from children's resolved constructs + own text signals.
Writes full results to logs/.

Construct taxonomy:
  container     — groups independent self-contained definitions; no Catala wrapper
  legal_concept — children are incomplete variants of one concept; → enumeration in Catala
  scope         — computes a result from inputs; "for purposes of", tests, elections
  definition    — default rule inside an enclosing scope ("In general")
  exception     — overrides a conclusion or excludes from a category
  structure     — bundles named fields that travel together
  leaf          — no children; raw prose
"""

import json
import os
import re
from datetime import UTC, datetime

TREE_FILE = "7701_tree.json"
LOG_DIR = "logs"

_TERM_OPENER = re.compile(r"^\s*(the terms?\s+\"|any term used\b)", re.IGNORECASE)

"""
Reasoning behind ordering:

- exception first — overrides everything; if a node says "shall not be treated as", that wins regardless of other signals
- definition second — "In general" is a fixed structural marker, unambiguous
- leaf third — no children is a hard structural fact, shouldn't be overridden by text matches on empty content
- container before legal_concept — if all children are self-defining term definitions, that's stronger evidence than a chapeau pattern
- legal_concept before structure — enum openers are more specific than "consisting of"
- structure before scope — structural grouping is more specific than the generic fallback
- scope last — default fallback for anything that has children but matched nothing specific
"""


def _exception_tags(header_l, chapeau_l, body_l, has_children):
    tags = []
    if re.search(r"\bexceptions?\b|\bspecial rules?\b", header_l):
        tags.append(
            ("exception", "header contains 'Exception(s)' or 'Special rule(s)'")
        )
    if re.search(r"\bexceptions?\b", chapeau_l):
        tags.append(("exception", "chapeau contains 'Exception(s)'"))
    # body patterns only meaningful on non-leaf nodes: on leaves, exclusionary
    # language is part of the definition, not a structural exception
    if has_children and re.search(r"shall not be treated as", body_l):
        tags.append(("exception", "body: 'shall not be treated as'"))
    if has_children and re.search(r"notwithstanding", body_l):
        tags.append(("exception", "body: 'notwithstanding'"))
    return tags


def _scope_tags(chapeau_l, body_l, has_in_general_child, has_children):
    tags = []
    if has_children and (
        re.search(r"for purposes of", chapeau_l)
        or re.search(r"for purposes of", body_l)
    ):
        tags.append(("scope_def", "chapeau/body: 'for purposes of'"))
    if has_in_general_child:
        tags.append(("scope_rule", "child named 'In general' or 'General rule'"))
    return tags


def _container_tags(raw_children, has_in_general_child, body, chapeau):
    tags = []
    _SPAN_ENDINGS = ("—", ":")
    if raw_children and (
        body.rstrip().endswith(_SPAN_ENDINGS)
        or chapeau.rstrip().endswith(_SPAN_ENDINGS)
    ):
        tags.append(
            ("container_intro", "body/chapeau ends '—'/';': introduces children")
        )
    is_bare = raw_children and not body.strip() and not chapeau.strip()
    if is_bare:
        tags.append(("container_bare", "no body/chapeau, structure in children"))
    has_dash = body.rstrip().endswith(("—", ":")) or chapeau.rstrip().endswith(
        ("—", ":")
    )
    if (
        not is_bare
        and not has_dash
        and len(raw_children) >= 2
        and not has_in_general_child
    ):
        all_self_defining = all(
            _TERM_OPENER.match(rc.get("body", ""))
            or _TERM_OPENER.match(rc.get("chapeau", ""))
            for rc in raw_children
        )
        if all_self_defining:
            tags.append(
                ("container_bare", "all children self-defining ('The term X means')")
            )
    return tags


def _legal_concept_tags(chapeau_l):
    enum_openers = [r"means—", r"\bis—", r"includes—", r"means any", r"is any"]
    for pat in enum_openers:
        if re.search(pat, chapeau_l):
            return [("legal_concept", f"chapeau matches '{pat}'")]
    return []


_TERM_INLINE = re.compile(r'the terms?\s+["\']', re.IGNORECASE)


def _definition_tags(body, chapeau):
    if _TERM_OPENER.match(body) or _TERM_OPENER.match(chapeau):
        return [("definition", "body/chapeau starts 'The term(s) X / Any term'")]
    if _TERM_INLINE.search(body) or _TERM_INLINE.search(chapeau):
        return [("definition", "body/chapeau contains 'the term \"X\"'")]
    return []


def _structure_tags(chapeau_l, has_children):
    if has_children and re.search(
        r"consisting of|shall include the following|composed of", chapeau_l
    ):
        return [("structure", "chapeau: 'consisting of / shall include'")]
    return []


def _has_def_child_tags(classified_children):
    if classified_children and any(
        any(t["construct"] == "definition" for t in c["tags"])
        for c in classified_children
    ):
        return [
            (
                "has_def_child",
                "at least one child has definition tag: parent is grouping wrapper",
            )
        ]
    return []


def classify_node(node):
    """
    Recursively classify node bottom-up.
    Accumulates all matching (construct, signal) tags, then resolves winner by priority.
    Returns dict with id, header, construct, signal, tags, children.
    """
    raw_children = node.get("children", [])

    classified_children = [classify_node(c) for c in raw_children]
    child_headers_l = [c["header"].lower().strip() for c in classified_children]

    header_l = node["header"].lower()
    chapeau_l = node["chapeau"].lower()
    body_l = node["body"].lower()

    has_in_general_child = (
        "in general" in child_headers_l or "general rule" in child_headers_l
    )

    tags = []

    if not raw_children:
        tags.append(("leaf", "no children"))

    tags.extend(_exception_tags(header_l, chapeau_l, body_l, bool(raw_children)))
    tags.extend(_definition_tags(node["body"], node["chapeau"]))
    tags.extend(
        _scope_tags(chapeau_l, body_l, has_in_general_child, bool(raw_children))
    )
    tags.extend(
        _container_tags(
            raw_children, has_in_general_child, node["body"], node["chapeau"]
        )
    )
    tags.extend(_structure_tags(chapeau_l, bool(raw_children)))

    tags.extend(_has_def_child_tags(classified_children))
    return _result(node, classified_children, tags)


def _result(node, classified_children, tags):
    return {
        "id": node["id"],
        "header": node["header"],
        "chapeau": node["chapeau"][:80],
        "child_count": len(classified_children),
        "tags": [{"construct": c, "signal": s} for c, s in tags],
        "children": classified_children,
    }


def walk_results(result):
    yield result
    for child in result.get("children", []):
        yield from walk_results(child)


def main():
    with open(TREE_FILE, encoding="utf-8") as f:
        tree = json.load(f)

    root = classify_node(tree)

    tag_counts = {}
    all_results = []

    for r in walk_results(root):
        for t in r["tags"]:
            tag_counts[t["construct"]] = tag_counts.get(t["construct"], 0) + 1
        flat = {k: v for k, v in r.items() if k != "children"}
        all_results.append(flat)

    os.makedirs(LOG_DIR, exist_ok=True)
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")

    json_path = os.path.join(LOG_DIR, f"classify_rules_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {"tag_counts": tag_counts, "results": all_results},
            f,
            indent=2,
            ensure_ascii=False,
        )

    txt_path = os.path.join(LOG_DIR, f"classify_rules_{timestamp}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=== Per-node tags ===\n")
        for r in all_results:
            tag_str = ", ".join(t["construct"] for t in r["tags"]) or "(none)"
            f.write(f"  {r['id']:35} [{tag_str}]\n")

        f.write("\n=== Tag frequency ===\n")
        f.writelines(
            f"  {v:3}  {k}\n"
            for k, v in sorted(tag_counts.items(), key=lambda x: -x[1])
        )

    print(f"Wrote {json_path}")
    print(f"Wrote {txt_path}")


if __name__ == "__main__":
    main()
