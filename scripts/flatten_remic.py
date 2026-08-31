#!/usr/bin/env python3
"""Flatten a nested REMIC JSON structure into a flat list of assets.

Usage:
    python scripts/flatten_remic.py <input.json> [output.json]

If output is not specified, prints to stdout.
"""

import json
import sys
from pathlib import Path


def flatten_assets(assets: list) -> list:
    """Recursively flatten a list of assets, descending into REMICs."""
    flat = []
    for asset in assets:
        if not isinstance(asset, dict) or len(asset) != 1:
            raise ValueError(f"Expected single-key dict, got: {asset}")
        [name, data] = next(iter(asset.items()))
        if name == "RemicInterest":
            # Descend into the REMIC's underlying assets, losing REMIC identity
            underlying = data.get("underlying_assets", [])
            flat.extend(flatten_assets(underlying))
        else:
            flat.append(asset)
    return flat


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.json> [output.json]", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    with open(input_path) as f:
        data = json.load(f)

    nested = data.get("remic_assets", [])
    flat = flatten_assets(nested)

    output = {
        "assets": flat
    }

    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"Wrote {len(flat)} flat assets to {output_path}")
    else:
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
