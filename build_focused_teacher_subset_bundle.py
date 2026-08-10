"""Build a focused coupled bundle around teacher-positive split windows."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import defaultdict
from pathlib import Path

import le_gra_mvp as mvp
from run_p3_6_teacher_decision_audit import _scenario_row
from trace_io import load_trace_bundle


ROOT = Path(__file__).resolve().parent


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_bundle_metadata(bundle_dir: Path) -> tuple[list[dict[str, str]], dict[str, list[dict[str, str]]]]:
    _, scenario_rows = _read_csv(bundle_dir / "scenarios.csv")
    _, user_rows = _read_csv(bundle_dir / "users.csv")
    users_by_scenario: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in user_rows:
        users_by_scenario[row["scenario_id"]].append(row)
    return scenario_rows, users_by_scenario


def _teacher_decision_rows(
    bundle_dir: Path,
    *,
    switch_beta: float,
    max_groups: int | None,
    feature_mode: str,
) -> list[dict[str, object]]:
    scenarios = load_trace_bundle(bundle_dir, feature_mode=feature_mode)
    scenario_rows, users_by_scenario = _load_bundle_metadata(bundle_dir)
    rows: list[dict[str, object]] = []
    for metadata, scenario in zip(scenario_rows, scenarios):
        user_rows = sorted(users_by_scenario[metadata["scenario_id"]], key=lambda row: int(row["user_index"]))
        if len(user_rows) < 2:
            continue
        teacher_groups = mvp.offline_teacher_groups(
            scenario,
            max_groups=max_groups or len(scenario.cqi_now),
            switch_beta=switch_beta,
        )
        rows.append(
            _scenario_row(
                {
                    "scenario_id": metadata["scenario_id"],
                    "timestamp_s": metadata["timestamp_s"],
                    "serving_gnb": metadata["serving_gnb"],
                    "ue_ids": "|".join(row["ue_id"] for row in user_rows),
                    "user_count": len(user_rows),
                },
                scenario,
                teacher_groups,
                switch_beta,
                split_name="focused_seed_scan",
            )
        )
    return rows


def _time_key(value: str | float) -> str:
    return f"{float(value):.6f}"


def _scenario_signature(row: dict[str, object]) -> tuple[str, str]:
    return str(row["serving_gnb"]), str(row["ue_ids"])


def _window_membership(
    rows: list[dict[str, object]],
    *,
    min_gain: float,
    min_group_count: int,
    time_margin_s: float,
) -> tuple[set[str], list[dict[str, object]], dict[tuple[str, str], list[float]]]:
    seed_rows = [
        row
        for row in rows
        if float(row["teacher_gain_vs_single"]) >= min_gain
        and int(row["teacher_group_count"]) >= min_group_count
    ]
    seed_windows: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in seed_rows:
        seed_windows[_scenario_signature(row)].append(float(row["timestamp_s"]))

    keep_ids: set[str] = set()
    for row in rows:
        signature = _scenario_signature(row)
        if signature not in seed_windows:
            continue
        ts = float(row["timestamp_s"])
        if any(abs(ts - anchor) <= time_margin_s + 1e-9 for anchor in seed_windows[signature]):
            keep_ids.add(str(row["scenario_id"]))
    return keep_ids, seed_rows, seed_windows


def _filter_by_scenario_ids(rows: list[dict[str, str]], keep_ids: set[str]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("scenario_id", "") in keep_ids]


def _filter_radio_like_rows(
    rows: list[dict[str, str]],
    keep_triplets: set[tuple[str, str, str]],
) -> list[dict[str, str]]:
    kept = []
    for row in rows:
        key = (_time_key(row["timestamp_s"]), row["serving_gnb"], row["ue_id"])
        if key in keep_triplets:
            kept.append(row)
    return kept


def _filter_mobility_scenarios(
    rows: list[dict[str, str]],
    keep_snapshot_keys: set[tuple[str, str]],
) -> list[dict[str, str]]:
    kept = []
    for row in rows:
        key = (_time_key(row["timestamp_s"]), row["serving_gnb"])
        if key in keep_snapshot_keys:
            kept.append(row)
    return kept


def _copy_or_filter_bundle(
    src_root: Path,
    dst_root: Path,
    keep_ids: set[str],
    keep_triplets: set[tuple[str, str, str]],
    keep_snapshot_keys: set[tuple[str, str]],
) -> dict[str, int]:
    summary: dict[str, int] = {}
    for rel_path in [Path("bundle/scenarios.csv"), Path("bundle/users.csv"), Path("bundle/rb_rates.csv")]:
        src = src_root / rel_path
        dst = dst_root / rel_path
        fields, rows = _read_csv(src)
        filtered = _filter_by_scenario_ids(rows, keep_ids)
        _write_csv(dst, fields, filtered)
        summary[str(rel_path)] = len(filtered)

    mobility_scenarios_path = Path("mobility/sumo_scenarios.csv")
    mobility_scenarios_fields, mobility_scenarios_rows = _read_csv(src_root / mobility_scenarios_path)
    filtered_mobility_scenarios = _filter_mobility_scenarios(
        mobility_scenarios_rows,
        keep_snapshot_keys,
    )
    _write_csv(dst_root / mobility_scenarios_path, mobility_scenarios_fields, filtered_mobility_scenarios)
    summary[str(mobility_scenarios_path)] = len(filtered_mobility_scenarios)

    mobility_rows_path = Path("mobility/sumo_mobility.csv")
    mobility_rows_fields, mobility_rows = _read_csv(src_root / mobility_rows_path)
    filtered_mobility_rows = _filter_radio_like_rows(mobility_rows, keep_triplets)
    _write_csv(dst_root / mobility_rows_path, mobility_rows_fields, filtered_mobility_rows)
    summary[str(mobility_rows_path)] = len(filtered_mobility_rows)

    for rel_path in [
        Path("radio/radio_users.csv"),
        Path("radio/radio_rbs.csv"),
        Path("radio/quality_state.csv"),
    ]:
        src = src_root / rel_path
        dst = dst_root / rel_path
        fields, rows = _read_csv(src)
        filtered = _filter_radio_like_rows(rows, keep_triplets)
        _write_csv(dst, fields, filtered)
        summary[str(rel_path)] = len(filtered)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, required=True, help="Coupled bundle root with bundle/radio/mobility")
    parser.add_argument("--out", type=Path, required=True, help="Focused subset bundle root")
    parser.add_argument("--feature-mode", default="history_cost_quality")
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--max-groups", type=int, default=None)
    parser.add_argument("--min-gain", type=float, default=1e-9)
    parser.add_argument("--min-group-count", type=int, default=2)
    parser.add_argument("--time-margin-s", type=float, default=0.0)
    args = parser.parse_args()

    src_root = (ROOT / args.src).resolve() if not args.src.is_absolute() else args.src.resolve()
    dst_root = (ROOT / args.out).resolve() if not args.out.is_absolute() else args.out.resolve()
    bundle_dir = src_root / "bundle"
    if not bundle_dir.exists():
        raise FileNotFoundError(f"Missing bundle directory: {bundle_dir}")
    if dst_root.exists():
        shutil.rmtree(dst_root)
    shutil.copytree(src_root, dst_root)

    decision_rows = _teacher_decision_rows(
        bundle_dir,
        switch_beta=args.switch_beta,
        max_groups=args.max_groups,
        feature_mode=args.feature_mode,
    )
    keep_ids, seed_rows, seed_windows = _window_membership(
        decision_rows,
        min_gain=args.min_gain,
        min_group_count=args.min_group_count,
        time_margin_s=args.time_margin_s,
    )

    _, scenario_rows = _read_csv(src_root / "bundle" / "scenarios.csv")
    _, kept_user_rows = _read_csv(src_root / "bundle" / "users.csv")
    kept_scenario_rows = _filter_by_scenario_ids(scenario_rows, keep_ids)
    keep_triplets = {
        (_time_key(scenario_row["timestamp_s"]), scenario_row["serving_gnb"], user_row["ue_id"])
        for scenario_row in kept_scenario_rows
        for user_row in kept_user_rows
        if user_row["scenario_id"] == scenario_row["scenario_id"]
    }
    keep_snapshot_keys = {
        (_time_key(row["timestamp_s"]), row["serving_gnb"])
        for row in kept_scenario_rows
    }

    filter_summary = _copy_or_filter_bundle(
        src_root,
        dst_root,
        keep_ids,
        keep_triplets,
        keep_snapshot_keys,
    )

    decision_fields = list(seed_rows[0].keys()) if seed_rows else []
    _write_csv(dst_root / "focused_seed_scenarios.csv", decision_fields, [
        {key: str(value) for key, value in row.items()}
        for row in sorted(seed_rows, key=lambda item: float(item["timestamp_s"]))
    ])

    manifest = {
        "source_bundle": str(src_root),
        "feature_mode": args.feature_mode,
        "switch_beta": args.switch_beta,
        "max_groups": args.max_groups,
        "min_gain": args.min_gain,
        "min_group_count": args.min_group_count,
        "time_margin_s": args.time_margin_s,
        "decision_row_count": len(decision_rows),
        "seed_scenario_count": len(seed_rows),
        "kept_scenario_count": len(keep_ids),
        "kept_family_count": len(seed_windows),
        "kept_windows": [
            {
                "serving_gnb": serving_gnb,
                "ue_ids": ue_ids,
                "seed_timestamps_s": sorted(timestamps),
            }
            for (serving_gnb, ue_ids), timestamps in sorted(seed_windows.items())
        ],
        "filtered_rows": filter_summary,
    }
    (dst_root / "focused_subset_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    metadata_path = dst_root / "radio" / "export_metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["focused_subset"] = manifest
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("Focused teacher subset bundle complete")
    print(f"  source={src_root}")
    print(f"  out={dst_root}")
    print(f"  teacher_decision_rows={len(decision_rows)}")
    print(f"  seed_scenarios={len(seed_rows)}")
    print(f"  kept_scenarios={len(keep_ids)}")
    print(f"  kept_families={len(seed_windows)}")
    for key, value in sorted(filter_summary.items()):
        print(f"  {key}={value}")


if __name__ == "__main__":
    main()
