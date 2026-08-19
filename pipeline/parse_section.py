"""
Parse any 26 USC section into a JSON tree from Cornell LII.
Each node: id, num, header, chapeau, body (div.content text), children.

Usage:
    python pipeline/parse_section.py 163          # §163 → data/163_tree.json
    python pipeline/parse_section.py 61 72 108    # multiple sections
"""

import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup, Tag

BASE_URL = "https://www.law.cornell.edu/uscode/text/26/{}"
DATA_DIR = "data"

LEVEL_CLASSES = [
    "subsection",
    "paragraph",
    "subparagraph",
    "clause",
    "subclause",
    "item",
    "subitem",
]


_CHAR_MAP = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})


def clean(tag):
    if tag is None:
        return ""
    return re.sub(r"\s+", " ", tag.get_text().translate(_CHAR_MAP)).strip()


def is_level_node(tag):
    return isinstance(tag, Tag) and any(lc in tag.get("class", []) for lc in LEVEL_CLASSES)  # type: ignore


def build_node(div, parent_id):
    num_span = div.find("span", class_="num", recursive=False)
    num = ""
    if num_span:
        num = clean(num_span).strip("()[]")
        if not num:
            raise RuntimeError(f"Empty num span under {parent_id}: {num_span}")

    node_id = f"{parent_id}({num})"
    header = clean(div.find("span", class_="heading", recursive=False))
    chapeau = clean(div.find("span", class_="chapeau", recursive=False))

    content_div = div.find("div", class_="content", recursive=False)
    body = clean(content_div) if content_div else ""

    children = []
    consumed_continuations: set[int] = set()
    search_in = content_div if content_div else div
    for child in search_in.children:
        if is_level_node(child):
            children.append(build_node(child, node_id))
        elif (
            isinstance(child, Tag)
            and "continuation" in (child.get("class") or [])
            and children
        ):
            # Continuation placed as sibling after the preceding level node in the HTML
            children[-1]["continuation"] = clean(child)
            consumed_continuations.add(id(child))

    continuation_div = div.find("div", class_="continuation", recursive=False)
    if continuation_div and id(continuation_div) in consumed_continuations:
        continuation = ""
    else:
        continuation = clean(continuation_div) if continuation_div else ""

    return {
        "id": node_id,
        "num": num,
        "header": header,
        "chapeau": chapeau,
        "body": body,
        "continuation": continuation,
        "children": children,
    }


def walk_all(node):
    yield node
    for child in node.get("children", []):
        yield from walk_all(child)


def scrape_section(section: str) -> dict:
    url = BASE_URL.format(section)
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    statute_div = soup.find("div", class_="section")
    if not statute_div:
        raise RuntimeError(f"§{section}: could not find div.section at {url}")

    heading_tag = soup.find("h1") or soup.find("h2")
    heading_text = clean(heading_tag) if heading_tag else f"26 U.S.C. § {section}"

    tree = {
        "id": section,
        "num": "",
        "header": heading_text,
        "chapeau": "",
        "body": "",
        "children": [],
    }

    for child in statute_div.children:
        if is_level_node(child):
            tree["children"].append(build_node(child, section))

    return tree


def main(sections: list[str]):
    import os

    os.makedirs(DATA_DIR, exist_ok=True)

    for i, section in enumerate(sections):
        out_path = f"{DATA_DIR}/{section}_tree.json"
        print(f"[{i+1}/{len(sections)}] §{section} ...", end=" ", flush=True)
        try:
            tree = scrape_section(section)
            total = sum(1 for _ in walk_all(tree))
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(tree, f, indent=2, ensure_ascii=False)
            print(f"OK — {total} nodes → {out_path}")
        except Exception as e:
            print(f"FAILED: {e}")

        if i < len(sections) - 1:
            time.sleep(1.2)


if __name__ == "__main__":
    if not sys.argv[1:]:
        sys.exit("Usage: parse_section.py <section> [section ...]")
    main(sys.argv[1:])
