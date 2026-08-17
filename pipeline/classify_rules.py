"""
Rule-based construct classifier for any scraped IRC section tree.
Bottom-up recursive walk: children classified before parent.
Parent construct determined from children's resolved constructs + own text signals.
Writes results to logs/classify/classify_rules_{section}.{json,txt} (overwrites).

Usage:
    python pipeline/classify_rules.py 7701
    python pipeline/classify_rules.py 101
"""

import argparse
import json
import os
import re

LOG_DIR = "logs/classify"

_SPAN_ENDINGS = ("—", ":")
_TERM_OPENER = re.compile(r"^\s*(the terms?\s+\"|any term used\b)", re.IGNORECASE)
_TERM_INLINE = re.compile(r'the terms?\s+["\']', re.IGNORECASE)

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
    if re.search(r"shall not\b", header_l):
        tags.append(("exception", "header: 'shall not'"))
    if re.search(r"\bexceptions?\b", chapeau_l):
        tags.append(("exception", "chapeau contains 'Exception(s)'"))
    # body patterns only meaningful on non-leaf nodes: on leaves, exclusionary
    # language is part of the definition, not a structural exception
    if has_children and re.search(r"shall not\b", body_l):
        tags.append(("exception", "body: 'shall not'"))
    if has_children and re.search(r"notwithstanding", body_l):
        tags.append(("exception", "body: 'notwithstanding'"))
    if re.search(r"shall not\b", chapeau_l):
        tags.append(("exception", "chapeau: 'shall not'"))
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
    if has_children and re.search(r"\bin the case of\b", chapeau_l):
        tags.append(
            (
                "scope_case",
                "chapeau: 'in the case of' — conditional classification scope",
            )
        )
    if has_children and re.search(r"\bif—", chapeau_l):
        tags.append(("scope_if", "chapeau: 'if—' — conditional scope"))
    if has_children and re.search(r"at least \d|an amount equal to", chapeau_l):
        tags.append(("scope_threshold", "chapeau: threshold or amount computation"))
    if has_children and re.search(
        r"except as otherwise provided|shall not apply", chapeau_l
    ):
        tags.append(("scope_override", "chapeau: exception/override scope"))
    return tags


def _admin_rule_tags(chapeau_l, body_l, has_children):
    pattern = r"(shall|may) (prescribe|issue|establish).{0,40}(regulations?|guidance)"
    if has_children and re.search(pattern, chapeau_l):
        return [
            ("admin_rule", "chapeau: administrative delegation — no Catala construct")
        ]
    if has_children and re.search(pattern, body_l):
        return [("admin_rule", "body: administrative delegation — no Catala construct")]
    return []


def _container_tags(raw_children, has_in_general_child, body, chapeau):
    tags = []
    if raw_children and (
        body.rstrip().endswith(_SPAN_ENDINGS)
        or chapeau.rstrip().endswith(_SPAN_ENDINGS)
    ):
        tags.append(
            ("container_intro", "body/chapeau ends '—'/':': introduces children")
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
    tags.extend(_admin_rule_tags(chapeau_l, body_l, bool(raw_children)))
    tags.extend(_has_def_child_tags(classified_children))
    return _result(node, classified_children, tags)


def _result(node, classified_children, tags):
    return {
        **{k: v for k, v in node.items() if k != "children"},
        "child_count": len(classified_children),
        "tags": [{"construct": c, "signal": s} for c, s in tags],
        "children": classified_children,
    }


def walk_results(result):
    yield result
    for child in result.get("children", []):
        yield from walk_results(child)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("section", help="IRC section number (e.g. 101)")
    args = parser.parse_args()

    tree_path = f"data/{args.section}_tree.json"
    if not os.path.exists(tree_path):
        parser.error(f"Tree file not found: {tree_path} — run parse_section.py {args.section} first")

    with open(tree_path, encoding="utf-8") as f:
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

    json_path = os.path.join(LOG_DIR, f"classify_rules_{args.section}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {"tag_counts": tag_counts, "results": all_results},
            f,
            indent=2,
            ensure_ascii=False,
        )

    txt_path = os.path.join(LOG_DIR, f"classify_rules_{args.section}.txt")
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
"""
Observations:
1. the file was made after checking section 7701 and more of the decisions were made based on the trends seens in that section. However, I have come to realize that most of these do not help demarket how to fold the children into the parent in order to prevent calling the agent on the children that return partial. This is not just to save the wasteful calls but to pass sufficient information. What is most useful is that whenever there is a chapeau and the children are just leaves followed by a continuation then the whole node can be treated as one body rather than calling on children again and again. However, there are certain properties that children must have. For example they should not be definitions. A very simple test is if children start with a capital letter or not. If they don't then they can be treated as part of a sentence being continued. The continuation that follows illustrates some other point so it is linked to the body. So while folding the children this needs to be done under some constraints. Other than that I don't find the scope tags or any other tags helpful
2. The 'shall not apply' has been repeated under exception tag and the scope tag. Need to fix that
3. 'In general' or 'General rule' separation is not useful in practice because that does not signal what follows will be an exception or not.
4. There are several types of exceptions possible. Limitations can double as exception in some cases, and in fact normal provision can contain hidden exception, so checking on keyword is not sufficient.
5. Structure tag was supposed to map to enum however I haven't seen any structure tag yet, probably because scope handles it so should be subsumed under scope.
6. Admin tags might be useful in a narrow sense. 
7. Definition tags are useful because definitions leafs cannot be folded into the body of the parent, even if one of the child is a definition it needs to be treated differently.
"""

