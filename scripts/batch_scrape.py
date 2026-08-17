"""
Scrape all target IRC sections from Cornell LII.

Skips sections where data/{section}_tree.json already exists (use --force to override).
Rate limited to ~1 request per 1.2s.

Usage:
    python scripts/batch_scrape.py
    python scripts/batch_scrape.py --force
    python scripts/batch_scrape.py --sections 61 72 163
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.parse_section import main as scrape_sections

# Sections selected for exception pattern analysis.
# 7701 already scraped; included so --force re-scrapes it too.
TARGET_SECTIONS = [
    "61",    # gross income — root of dependency graph
    "72",    # annuities — complex input vs output edge interaction
    "101",   # exclusions from gross income (life insurance, gifts)
    "104",   # compensation for injuries/sickness
    "108",   # discharge of indebtedness — multiple notwithstanding clauses
    "152",   # dependent definition — definitional exception patterns
    "162",   # trade/business expenses
    "163",   # interest incl. (j) — explicit "notwithstanding any other provision"
    "168",   # MACRS depreciation — structured with many special rules
    "318",   # constructive ownership — clean exception structure
    "469",   # passive activity — overlapping independent tests + carve-outs
    "1001",  # recognition of gain/loss — nonrecognition as output override
    "1245",  # depreciation recapture — overrides nonrecognition provisions
    "7701",  # definitions (already have; re-scrape with --force)
    "7872",  # below market loans — temporal elements + imputed interest
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-scrape even if file exists")
    parser.add_argument("--sections", nargs="+", help="Override section list")
    args = parser.parse_args()

    sections = args.sections or TARGET_SECTIONS

    existing = [s for s in sections if os.path.exists(f"data/{s}_tree.json")]
    if existing and not args.force:
        print(f"Skipping (already exist): {', '.join('§' + s for s in existing)}")
        sections = [s for s in sections if s not in existing]

    if not sections:
        print("Nothing to scrape.")
        return

    scrape_sections(sections)


if __name__ == "__main__":
    main()
