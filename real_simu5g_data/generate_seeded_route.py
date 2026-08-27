"""Generate auditable per-vehicle mobility variation for a P3.7 seed."""

from __future__ import annotations

import argparse
import json
import random
import xml.etree.ElementTree as ET
from pathlib import Path


MEAN = 1.0
STD = 0.08
MIN_FACTOR = 0.85
MAX_FACTOR = 1.15


def build(input_path: Path, output_path: Path, metadata_path: Path, seed: int) -> None:
    tree = ET.parse(input_path)
    root = tree.getroot()
    base_type = root.find("vType[@id='car']")
    if base_type is None:
        raise ValueError("input route must contain vType id='car'")

    vehicles = root.findall("vehicle")
    if not vehicles:
        raise ValueError("route file has no <vehicle> entries")

    rng = random.Random(seed)
    factors: dict[str, float] = {}
    insert_at = list(root).index(base_type)
    root.remove(base_type)

    for offset, vehicle in enumerate(vehicles):
        vehicle_id = vehicle.attrib["id"]
        factor = min(MAX_FACTOR, max(MIN_FACTOR, rng.normalvariate(MEAN, STD)))
        type_id = f"car_seed_{vehicle_id}"
        attributes = dict(base_type.attrib)
        attributes["id"] = type_id
        attributes["speedFactor"] = f"{factor:.8f}"
        root.insert(insert_at + offset, ET.Element("vType", attributes))
        vehicle.attrib["type"] = type_id
        factors[vehicle_id] = round(factor, 8)

    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="unicode", xml_declaration=False)
    metadata_path.write_text(
        json.dumps(
            {
                "generator": "generate_seeded_route.py",
                "seed": seed,
                "distribution": {
                    "name": "clipped_normal",
                    "mean": MEAN,
                    "std": STD,
                    "min": MIN_FACTOR,
                    "max": MAX_FACTOR,
                },
                "vehicle_speed_factors": factors,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    if args.seed < 0:
        raise SystemExit("seed must be non-negative")
    build(args.input, args.output, args.metadata, args.seed)


if __name__ == "__main__":
    main()
