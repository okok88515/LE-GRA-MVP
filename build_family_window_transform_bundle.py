"""Declarative family-window bundle transformer for structural data design.

This is a reusable scaffold for the current P3.6q phase, where the main need
is no longer isolated one-off tweaks, but a repeatable way to generate new
bundle variants from explicit per-family, per-window structural specs.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path


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


def _clip_cqi(value: float) -> float:
    return max(1.0, min(15.0, value))


def _load_spec(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _matching_target_scenarios(
    bundle_root: Path,
    *,
    serving_gnb: str,
    target_ue_ids: str,
    window_start_s: float,
    window_end_s: float,
) -> dict[str, float]:
    _, scenario_rows = _read_csv(bundle_root / "bundle" / "scenarios.csv")
    _, user_rows = _read_csv(bundle_root / "bundle" / "users.csv")
    users_by_scenario: dict[str, list[dict[str, str]]] = {}
    for row in user_rows:
        users_by_scenario.setdefault(row["scenario_id"], []).append(row)

    matched: dict[str, float] = {}
    for row in scenario_rows:
        ts = float(row["timestamp_s"])
        if row["serving_gnb"] != serving_gnb or ts < window_start_s - 1e-9 or ts > window_end_s + 1e-9:
            continue
        family = sorted(
            users_by_scenario.get(row["scenario_id"], []),
            key=lambda item: int(item["user_index"]),
        )
        if "|".join(item["ue_id"] for item in family) == target_ue_ids:
            matched[row["scenario_id"]] = ts
    return matched


def _window_rule(ts: float, windows: list[dict]) -> dict | None:
    for window in windows:
        if float(window["start_s"]) - 1e-9 <= ts <= float(window["end_s"]) + 1e-9:
            return window
    return None


def _apply_user_rule(row: dict[str, str], ue_rule: dict) -> None:
    current = float(row["cqi_now_raw"])
    if "previous_quality" in ue_rule:
        row["previous_quality"] = str(int(ue_rule["previous_quality"]))
    current += float(ue_rule.get("cqi_now_delta", 0.0))
    if "cqi_now_raw" in ue_rule:
        current = float(ue_rule["cqi_now_raw"])
    current = _clip_cqi(current)
    row["cqi_now_raw"] = f"{current:.2f}"
    row["cqi_now"] = str(int(round(current)))

    if "history_offsets" in ue_rule:
        offsets = list(ue_rule["history_offsets"])
        if len(offsets) != 4:
            raise ValueError("history_offsets must have length 4")
        row["cqi_t_minus_4"] = f"{_clip_cqi(current + float(offsets[0])):.2f}"
        row["cqi_t_minus_3"] = f"{_clip_cqi(current + float(offsets[1])):.2f}"
        row["cqi_t_minus_2"] = f"{_clip_cqi(current + float(offsets[2])):.2f}"
        row["cqi_t_minus_1"] = f"{_clip_cqi(current + float(offsets[3])):.2f}"


def _apply_rate_rule(rate_kbps: float, ue_rule: dict) -> float:
    if "rb_scale" in ue_rule:
        return max(1.0, rate_kbps * float(ue_rule["rb_scale"]))
    return rate_kbps


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args()

    spec = _load_spec(args.spec)
    src = ROOT / spec["base_bundle"]
    dst = ROOT / spec["out_dir"]
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    family = spec["family"]
    target_scenarios = _matching_target_scenarios(
        dst,
        serving_gnb=family["serving_gnb"],
        target_ue_ids=family["target_ue_ids"],
        window_start_s=float(family["window_start_s"]),
        window_end_s=float(family["window_end_s"]),
    )
    windows = spec["windows"]

    users_path = dst / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(users_path)
    touched_user_rows = 0
    for row in user_rows:
        ts = target_scenarios.get(row["scenario_id"])
        if ts is None:
            continue
        window = _window_rule(ts, windows)
        if window is None:
            continue
        ue_rule = window.get("ue_rules", {}).get(row["ue_id"])
        if ue_rule is None:
            continue
        _apply_user_rule(row, ue_rule)
        touched_user_rows += 1
    _write_csv(users_path, user_fields, user_rows)

    rate_touch_summary: dict[str, int] = {}
    for rel_dir, filename in [("bundle", "rb_rates.csv"), ("radio", "radio_rbs.csv")]:
        path = dst / rel_dir / filename
        fields, rows = _read_csv(path)
        modified = 0
        for row in rows:
            scenario_id = row.get("scenario_id", "")
            ts = target_scenarios.get(scenario_id)
            if ts is None:
                continue
            window = _window_rule(ts, windows)
            if window is None:
                continue
            ue_rule = window.get("ue_rules", {}).get(row["ue_id"])
            if ue_rule is None:
                continue
            new_rate = _apply_rate_rule(float(row["rate_kbps"]), ue_rule)
            row["rate_kbps"] = f"{new_rate:.6f}"
            modified += 1
        _write_csv(path, fields, rows)
        rate_touch_summary[f"{rel_dir}_{filename}"] = modified

    metadata_path = dst / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": spec["name"],
        "base_bundle": spec["base_bundle"],
        "family": family,
        "intent": spec.get("intent", ""),
        "windows": windows,
        "generated_from_spec": str(args.spec.name),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print(f"{spec['name']} bundle:")
    print(f"  out_dir={dst}")
    print(f"  target_scenarios={len(target_scenarios)}")
    print(f"  touched_user_rows={touched_user_rows}")
    for key, value in rate_touch_summary.items():
        print(f"  {key}_modified={value}")


if __name__ == "__main__":
    main()
