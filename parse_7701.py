"""
Parse 26 USC § 7701 hierarchy.
Capture all level nodes (heading + chapeau). No period filter.
Output indented by level using original symbols: a, 1, A, i, I, aa, AA.
"""

import requests
from bs4 import BeautifulSoup
import re

URL = "https://www.law.cornell.edu/uscode/text/26/7701"
OUTPUT_FILE = "7701_parsed.txt"
INDENT = "  "  # 2 spaces per level

# CSS class → level index (0-based)
LEVEL_CLASSES = [
    "subsection",    # L1: a, b, c
    "paragraph",     # L2: 1, 2, 3
    "subparagraph",  # L3: A, B, C
    "clause",        # L4: i, ii, iii
    "subclause",     # L5: I, II, III
    "item",          # L6: aa, bb, cc
    "subitem",       # L7: AA, BB, CC
]


def clean(tag):
    return re.sub(r"\s+", " ", tag.get_text()).strip()


def process_node(node, depth, results):
    """
    depth: 0-based depth matching LEVEL_CLASSES index.
    """
    if not hasattr(node, "attrs"):
        return

    classes = node.get("class", [])
    matched_level_idx = None
    for idx, lc in enumerate(LEVEL_CLASSES):
        if lc in classes:
            matched_level_idx = idx
            break

    if matched_level_idx is not None:
        # Get num value from span.num (direct child)
        num_val = ""
        num_span = node.find("span", class_="num", recursive=False)
        if num_span:
            num_val = num_span.get("value", "").strip() or clean(num_span).strip("()")

        # heading and chapeau — direct children only, no div.content p tags
        heading_span = node.find("span", class_="heading", recursive=False)
        chapeau_span = node.find("span", class_="chapeau", recursive=False)

        heading_text = clean(heading_span) if heading_span else ""
        chapeau_text = clean(chapeau_span) if chapeau_span else ""

        combined = " ".join(filter(None, [heading_text, chapeau_text])).strip()

        indent = INDENT * matched_level_idx
        line = f"{indent}({num_val})" + (f" {combined}" if combined else "")
        results.append(line)

        # Recurse into children (skip div.content entirely)
        for child in node.children:
            if hasattr(child, "attrs"):
                child_classes = child.get("class", [])
                if "content" in child_classes:
                    continue  # skip div.content and its <p> children
                process_node(child, matched_level_idx + 1, results)
        return

    # Not a level node — recurse at same depth
    for child in node.children:
        process_node(child, depth, results)


def main():
    r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    statute_div = soup.find("div", class_="section")
    if not statute_div:
        raise RuntimeError("Could not find div.section in page")

    results = []
    process_node(statute_div, 0, results)

    output = "\n".join(results)
    print(output)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output + "\n")

    print(f"\n--- saved to {OUTPUT_FILE} ---")


if __name__ == "__main__":
    main()
