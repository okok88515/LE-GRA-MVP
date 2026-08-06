"""P3.6m-4 sweep around the positive-family decoy regime.

Goal:
- start from the successful P3.6m-2 decoy-positive family
- replicate more nearby temporal slices by sweeping
  - the decoy activation start time
  - the decoy rate penalty
  - the decoy history drop

For speed, this script evaluates only the target family instead of running a
full audit on every variant. Once a promising variant is found, we can promote
it to a full audit and learner run.
"""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import le_gra_mvp as mvp
from run_p3_6_coupled_learner import _subset_scenarios


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6i2_coupled_bundle"
OUT = ROOT / "p3_6m4_slice_sweep"
TARGET_GNB = "gnb_1"
TARGET_UE_IDS = "0|1|15|2|3|4|5"
TARGET_FOCUS_IDS = TARGET_UE_IDS.split("|")
PRIMARY_UE_ID = "15"
DECOY_UE_ID = "4"
PRIMARY_LOCAL_INDEX = 2
DECOY_LOCAL_INDEX = 5
END_S = 43.9
START_S = 38.0


@dataclass(frozen=True)
class Variant:
    name: str
    window_start_s: float
    hi_factor: float
    mid_factor: float
    low_factor: float
    decoy_drop: float
    decoy_prev2_offset: float
    primary_drop: float


VARIANTS = [
    Variant("baseline_m2_like", 43.4, 0.985, 0.980, 0.990, 1.0, 0.1, 1.4),
    Variant("start_43_3_same", 43.3, 0.985, 0.980, 0.990, 1.0, 0.1, 1.4),
    Variant("start_43_2_same", 43.2, 0.985, 0.980, 0.990, 1.0, 0.1, 1.4),
    Variant("start_43_4_medium", 43.4, 0.980, 0.975, 0.985, 1.2, 0.0, 1.5),
    Variant("start_43_3_medium", 43.3, 0.980, 0.975, 0.985, 1.2, 0.0, 1.5),
    Variant("start_43_4_stronger", 43.4, 0.975, 0.970, 0.982, 1.3, -0.1, 1.6),
]


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _clip_cqi(value: float) -> float:
    return max(1.0, min(15.0, value))


def _factor(rate_kbps: float, variant: Variant) -> float:
    if rate_kbps >= 1128.0:
        return variant.hi_factor
    if rate_kbps >= 984.0:
        return variant.mid_factor
    return variant.low_factor


def _matching_target_scenarios(bundle_root: Path, *, window_start_s: float) -> set[str]:
    _, scenario_rows = _read_csv(bundle_root / "bundle" / "scenarios.csv")
    _, user_rows = _read_csv(bundle_root / "bundle" / "users.csv")
    scenario_users: dict[str, list[dict[str, str]]] = {}
    for row in user_rows:
        scenario_users.setdefault(row["scenario_id"], []).append(row)

    target_ids: set[str] = set()
    for row in scenario_rows:
        timestamp_s = float(row["timestamp_s"])
        if row["serving_gnb"] != TARGET_GNB or not (window_start_s <= timestamp_s <= END_S):
            continue
        family = sorted(
            scenario_users.get(row["scenario_id"], []),
            key=lambda item: int(item["user_index"]),
        )
        if "|".join(item["ue_id"] for item in family) == TARGET_UE_IDS:
            target_ids.add(row["scenario_id"])
    return target_ids


def build_variant(variant: Variant) -> Path:
    dst = OUT / variant.name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(SRC, dst)

    target_scenario_ids = _matching_target_scenarios(dst, window_start_s=variant.window_start_s)

    for rel_dir, filename in [("bundle", "rb_rates.csv"), ("radio", "radio_rbs.csv")]:
        path = dst / rel_dir / filename
        fields, rows = _read_csv(path)
        for row in rows:
            if "scenario_id" in row:
                if row["scenario_id"] not in target_scenario_ids or row["ue_id"] != DECOY_UE_ID:
                    continue
            else:
                timestamp_s = float(row["timestamp_s"])
                if (
                    row["serving_gnb"] != TARGET_GNB
                    or not (variant.window_start_s <= timestamp_s <= END_S)
                    or row["ue_id"] != DECOY_UE_ID
                ):
                    continue
            rate = float(row["rate_kbps"])
            row["rate_kbps"] = f"{max(1.0, rate * _factor(rate, variant)):.6f}"
        _write_csv(path, fields, rows)

    users_path = dst / "bundle" / "users.csv"
    fields, rows = _read_csv(users_path)
    for row in rows:
        if row["scenario_id"] not in target_scenario_ids:
            continue
        current = float(row["cqi_now_raw"])
        if row["ue_id"] == DECOY_UE_ID:
            row["cqi_t_minus_4"] = f"{_clip_cqi(current + 0.9):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(current + 0.6):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(current + variant.decoy_prev2_offset):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(current - variant.decoy_drop):.2f}"
        elif row["ue_id"] == PRIMARY_UE_ID:
            row["cqi_t_minus_4"] = f"{_clip_cqi(current + 1.0):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(current + 0.6):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(current + 0.2):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(current - variant.primary_drop):.2f}"
    _write_csv(users_path, fields, rows)

    metadata_path = dst / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": variant.name,
        "base_bundle": SRC.name,
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "window_s": [variant.window_start_s, END_S],
        "intent": "P3.6m-4 slice sweep around the positive-family decoy regime",
        "ue4_rate_factors": {
            ">=1128_kbps": variant.hi_factor,
            ">=984_kbps": variant.mid_factor,
            "else": variant.low_factor,
        },
        "ue4_history": {
            "decoy_drop": variant.decoy_drop,
            "decoy_prev2_offset": variant.decoy_prev2_offset,
        },
        "ue15_history": {
            "primary_drop": variant.primary_drop,
        },
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return dst


def _parse_groups(text: str) -> list[list[int]]:
    return [[int(value) for value in group] for group in json.loads(text)]


def _group_contains_dualweak(groups: list[list[int]]) -> bool:
    return any(
        PRIMARY_LOCAL_INDEX in group and DECOY_LOCAL_INDEX in group and len(group) < len(TARGET_FOCUS_IDS)
        for group in groups
    )


def evaluate_variant(bundle_root: Path, variant: Variant) -> tuple[list[dict[str, str]], dict[str, str]]:
    scenarios, metadata_rows = _subset_scenarios(
        bundle_root / "bundle",
        set(TARGET_FOCUS_IDS),
        "history_cost_quality",
        min_users=2,
    )
    rows: list[dict[str, str]] = []
    positive = 0
    positive_dualweak = 0
    multi_group = 0
    first_positive_time = ""
    for scenario, metadata in zip(scenarios, metadata_rows):
        if metadata["ue_ids"] != TARGET_UE_IDS or metadata["serving_gnb"] != TARGET_GNB:
            continue
        teacher_groups = mvp.offline_teacher_groups(scenario, max_groups=3, switch_beta=0.5)
        teacher_result = mvp.allocate_and_evaluate(teacher_groups, scenario, 0.5)
        single_result = mvp.allocate_and_evaluate([list(range(len(scenario.cqi_now)))], scenario, 0.5)
        gain = float(teacher_result.utility - single_result.utility)
        groups_json = json.dumps([sorted(group) for group in teacher_groups])
        dualweak = _group_contains_dualweak(teacher_groups)
        if len(teacher_groups) > 1:
            multi_group += 1
        if gain > 1e-9:
            positive += 1
            if not first_positive_time:
                first_positive_time = metadata["timestamp_s"]
        if gain > 1e-9 and dualweak:
            positive_dualweak += 1
        rows.append(
            {
                "timestamp_s": metadata["timestamp_s"],
                "teacher_group_count": str(len(teacher_groups)),
                "teacher_groups": groups_json,
                "teacher_gain_vs_single": f"{gain:.12f}",
                "is_dualweak_group": str(dualweak),
            }
        )

    max_gain = max((float(row["teacher_gain_vs_single"]) for row in rows), default=0.0)
    summary = {
        "variant": variant.name,
        "window_start_s": f"{variant.window_start_s:.1f}",
        "target_scenario_count": str(len(rows)),
        "multi_group_count": str(multi_group),
        "positive_gain_count": str(positive),
        "positive_dualweak_count": str(positive_dualweak),
        "max_gain_vs_single": f"{max_gain:.12f}",
        "first_positive_time_s": first_positive_time,
    }
    return rows, summary


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, str]] = []
    for variant in VARIANTS:
        bundle_root = build_variant(variant)
        timeline_rows, summary = evaluate_variant(bundle_root, variant)
        summary_rows.append(summary)
        _write_csv(bundle_root / "target_family_timeline.csv", list(timeline_rows[0].keys()), timeline_rows)

    summary_rows.sort(
        key=lambda row: (
            -int(row["positive_dualweak_count"]),
            -int(row["positive_gain_count"]),
            -float(row["max_gain_vs_single"]),
            row["window_start_s"],
        )
    )
    for index, row in enumerate(summary_rows, start=1):
        row["rank"] = str(index)

    _write_csv(OUT / "variant_summary.csv", list(summary_rows[0].keys()), summary_rows)
    (OUT / "summary.txt").write_text(
        "\n".join(
            [
                f"variant_count={len(summary_rows)}",
                f"best_variant={summary_rows[0]['variant']}" if summary_rows else "best_variant=",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"variant_count={len(summary_rows)}")
    if summary_rows:
        print(
            "best_variant="
            f"{summary_rows[0]['variant']} "
            f"(positive_dualweak_count={summary_rows[0]['positive_dualweak_count']}, "
            f"positive_gain_count={summary_rows[0]['positive_gain_count']}, "
            f"max_gain={summary_rows[0]['max_gain_vs_single']})"
        )


if __name__ == "__main__":
    main()
