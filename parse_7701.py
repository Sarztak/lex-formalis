"""
Parse 26 USC § 7701 into a JSON tree.
Each node: id, num, header, chapeau, body (div.content text), children.
"""

import requests
from bs4 import BeautifulSoup
import re
import json

URL = "https://www.law.cornell.edu/uscode/text/26/7701"
OUTPUT_FILE = "7701_tree.json"

LEVEL_CLASSES = [
    "subsection", "paragraph", "subparagraph",
    "clause", "subclause", "item", "subitem",
]


def clean(tag):
    if tag is None:
        return ""
    return re.sub(r"\s+", " ", tag.get_text()).strip()


def is_level_node(tag):
    return hasattr(tag, "attrs") and any(lc in tag.get("class", []) for lc in LEVEL_CLASSES)


def build_node(div, parent_id="7701"):
    num_span = div.find("span", class_="num", recursive=False)
    num = ""
    if num_span:
        num = num_span.get("value", "").strip() or clean(num_span).strip("()")

    node_id = f"{parent_id}({num})" if num else parent_id
    header = clean(div.find("span", class_="heading", recursive=False))
    chapeau = clean(div.find("span", class_="chapeau", recursive=False))

    content_div = div.find("div", class_="content", recursive=False)
    body = clean(content_div) if content_div else ""

    children = []
    search_in = content_div if content_div else div
    for child in search_in.children:
        if is_level_node(child):
            children.append(build_node(child, node_id))

    return {
        "id": node_id,
        "num": num,
        "header": header,
        "chapeau": chapeau,
        "body": body,
        "children": children,
    }


def main():
    r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    statute_div = soup.find("div", class_="section")
    if not statute_div:
        raise RuntimeError("Could not find div.section")

    tree = {
        "id": "7701",
        "num": "",
        "header": "26 U.S.C. § 7701 — Definitions",
        "chapeau": "",
        "body": "",
        "children": [],
    }

    for child in statute_div.children:
        if is_level_node(child):
            tree["children"].append(build_node(child, "7701"))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)

    total = sum(1 for _ in walk_all(tree))
    print(f"Saved to {OUTPUT_FILE}")
    print(f"Top-level subsections: {len(tree['children'])}")
    print(f"Total nodes: {total}")


def walk_all(node):
    yield node
    for child in node.get("children", []):
        yield from walk_all(child)


if __name__ == "__main__":
    main()
