"""
Generate deterministic names for construct-candidate nodes.
Hybrid: quoted-term regex → header → spaCy noun chunks (filtered) → ID fallback.
Run once; outputs logs/names_<timestamp>.json (id → name) and matching .txt.

spaCy is given chapeau+body combined. All noun chunks are inspected; single-word
generic results are rejected. Parent name is threaded through so children with
generic headers get parent_name+GenericHeader instead of duplicating parent.
"""

import json
import os
import re
import sys
from datetime import UTC, datetime

import spacy

CLASSIFY_LOG = "logs/classify/classify_rules_20260730_215825.json"
CONSTRUCT_TAGS = {"scope_rule", "scope_def", "container_intro", "container_bare"}

STOP_WORDS = {
    "a",
    "an",
    "the",
    "of",
    "or",
    "and",
    "in",
    "for",
    "to",
    "as",
    "by",
    "with",
    "is",
    "are",
    "not",
    "any",
    "such",
    "which",
    "where",
    "when",
    "if",
    "at",
    "be",
    "that",
    "this",
}

GENERIC_HEADERS = {
    "in general",
    "general rule",
    "general",
    "exception",
    "exceptions",
    "special rule",
    "special rules",
}

# openers whose first noun is structural boilerplate, not a concept name
_STRUCTURAL_OPENER = re.compile(
    r"^(for purposes of|except as|notwithstanding|in the case of|"
    r"with respect to|at least|in addition to|subject to|pursuant to|"
    r"during|which|who|both|an amount equal to|not later than)",
    re.IGNORECASE,
)

# spaCy noun chunks that are legal boilerplate
_USELESS_CHUNKS = {
    "term",
    "terms",
    "purposes",
    "case",
    "respect",
    "paragraph",
    "subparagraph",
    "clause",
    "subclause",
    "provision",
    "section",
    "subsection",
    "addition",
    "manner",
    "amount",
    "period",
    "december",
    "certification",
    "treatment",
    "coordination",
    "references",
    "secretary",
    "individual",
    "person",
    "corporation",
    "trust",
    "both",
    "who",
    "taxpayer",
}

_QUOTED_TERM = re.compile(r'[Tt]he terms?\s+"([^"]+)"')

# minimum content words for a spaCy result to be accepted
_MIN_CONTENT_WORDS = 2


def _to_camel(text):
    text = re.sub(r"[^a-zA-Z\s]", " ", text)
    words = text.split()
    words = [w for w in words if w.lower() not in STOP_WORDS] or words
    seen: set[str] = set()
    deduped = []
    for w in words:
        if w.lower() not in seen:
            seen.add(w.lower())
            deduped.append(w)
    return "".join(w.capitalize() for w in deduped)


def _id_to_name(node_id):
    # "7701(a)(12)(A)(i)" → "Sec7701_a_12_A_i"
    parts = re.findall(r"[^()]+", node_id)
    return "Sec" + "_".join(parts)


def _camel_word_count(name):
    return len(re.findall(r"[A-Z][a-z0-9]*", name))


def _spacy_name(nlp, text):
    """Return best noun chunk from text, or None if nothing useful found."""
    if not text or _STRUCTURAL_OPENER.match(text.strip()):
        return None
    best = None
    best_words = 0
    for chunk in nlp(text).noun_chunks:
        camel = _to_camel(chunk.text)
        content_words = [w for w in chunk.text.split() if w.lower() not in STOP_WORDS]
        if (
            camel.lower() not in _USELESS_CHUNKS
            and len(content_words) >= _MIN_CONTENT_WORDS
            and len(content_words) > best_words
        ):
            best = camel
            best_words = len(content_words)
    return best


def _raw_name(nlp, node_id, header, chapeau, body):
    """Generate name without parent context."""
    header_l = header.strip().lower()

    m = _QUOTED_TERM.search(chapeau)
    if m:
        return _to_camel(m.group(1))

    m = _QUOTED_TERM.search(body)
    if m:
        return _to_camel(m.group(1))

    if header_l and header_l not in GENERIC_HEADERS:
        return _to_camel(header)

    combined = " ".join(filter(None, [chapeau, body]))
    name = _spacy_name(nlp, combined)
    if name:
        return name

    return _id_to_name(node_id)


def _ancestor_names(node_id, name_map):
    names = set()
    pid = _parent_id(node_id)
    while pid:
        if pid in name_map:
            names.add(name_map[pid])
        pid = _parent_id(pid)
    return names


def extract_name(nlp, node_id, header, chapeau, body, name_map=None):
    chapeau = chapeau or ""
    body = body or ""
    header = header or ""

    name = _raw_name(nlp, node_id, header, chapeau, body)

    if (
        _camel_word_count(name) > 5
        or name_map
        and name in _ancestor_names(node_id, name_map)
    ):
        name = _id_to_name(node_id)

    return name


def walk(node):
    yield node
    for child in node.get("children", []):
        yield from walk(child)


def _parent_id(node_id):
    """Return parent ID by stripping last segment, or None for root."""
    m = re.match(r"^(.*)\([^)]+\)$", node_id)
    return m.group(1) if m else None


def main():
    nlp = spacy.load("en_core_web_sm")

    with open(CLASSIFY_LOG) as f:
        data = json.load(f)

    with open("data/7701_tree.json") as f:
        tree_data = json.load(f)

    node_map = {n["id"]: n for n in walk(tree_data)}

    # build construct tag set per id
    construct_ids = {}
    for entry in data["results"]:
        tags = {t["construct"] for t in entry.get("tags", [])}
        hit = tags & CONSTRUCT_TAGS
        if hit:
            construct_ids[entry["id"]] = sorted(hit)

    # process top-down so parent names are available for children
    name_map = {}
    rows = []
    for entry in data["results"]:
        nid = entry["id"]
        if nid not in construct_ids:
            continue
        node = node_map.get(nid, {})
        name = extract_name(
            nlp,
            nid,
            node.get("header", ""),
            node.get("chapeau", ""),
            node.get("body", ""),
            name_map=name_map,
        )
        name_map[nid] = name
        rows.append((nid, construct_ids[nid], name))

    ts = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")

    os.makedirs("logs/names", exist_ok=True)
    json_path = f"logs/names/names_{ts}.json"
    with open(json_path, "w") as f:
        json.dump(name_map, f, indent=2, ensure_ascii=False)

    lines = [
        f"Construct-candidate nodes: {len(rows)}",
        "",
        f"{'ID':<25} {'TAGS':<50} NAME",
        "-" * 115,
    ]
    for nid, tags, name in rows:
        lines.append(f"{nid:<25} {tags!s:<50} {name}")
    txt = "\n".join(lines)

    txt_path = f"logs/names/names_{ts}.txt"
    with open(txt_path, "w") as f:
        f.write(txt + "\n")

    print(txt)
    print(f"\nJSON: {json_path}", file=sys.stderr)
    print(f"TXT:  {txt_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
