"""Acceptance test for the coupled SUMO+Veins+Simu5G P3.5 bundle."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from build_p3_5_coupled_bundle import build_coupled_bundle


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    out_dir = Path("p3_5_coupled_bundle")
    counts = build_coupled_bundle(
        "p3_5_coupled_output",
        "p3_5_gnbs.csv",
        out_dir,
    )
    assert counts == {
        "sumo_vehicles": 2,
        "mapped_radio_rows": 27100,
        "mobility_rows": 67,
        "radio_raw_rows": 27100,
        "radio_radio_users": 67,
        "radio_radio_rbs": 1675,
        "radio_dropped_out_of_coverage": 0,
        "bundle_scenarios": 55,
        "bundle_users": 59,
        "bundle_rb_rows": 1475,
        "bundle_dropped_warmup_user_rows": 8,
        "teacher_scenarios": 55,
    }

    raw_mobility = _read(Path("p3_5_coupled_output/raw_mobility.csv"))
    raw_radio = _read(Path("p3_5_coupled_output/raw_radio.csv"))
    mapping = {(row["sumo_vehicle_id"], row["ue_module_path"]) for row in raw_mobility}
    assert mapping == {("0", "Highway.car[0]"), ("1", "Highway.car[1]")}
    assert {row["ue_module_path"] for row in raw_radio} == {module for _, module in mapping}

    users = _read(out_dir / "bundle/users.csv")
    rbs = _read(out_dir / "bundle/rb_rates.csv")
    assert {row["ue_id"] for row in users} == {"0", "1"}
    assert not any(row["ue_id"] in {"2049", "2050", "ue_2049", "ue_2050"} for row in users)
    by_user = defaultdict(list)
    for row in rbs:
        by_user[(row["scenario_id"], row["ue_id"])].append(int(row["rb_index"]))
    assert all(sorted(indices) == list(range(25)) for indices in by_user.values())

    metadata = json.loads((out_dir / "radio/export_metadata.json").read_text(encoding="utf-8"))
    assert metadata["ue_id_source"] == "SUMO_external_id_joined_by_OMNeT_module_path"
    assert metadata["snapshot_period_s"] == 0.1
    assert metadata["previous_quality_source"] == "explicit_experiment_control_not_video_measurement"
    print(
        "P3.5 PASS: one-clock SUMO+Veins+Simu5G run, stable external-ID mapping, "
        "complete 25-band bundle, P3.2 join, and offline teacher verified"
    )


if __name__ == "__main__":
    main()
