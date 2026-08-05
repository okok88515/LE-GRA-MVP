"""Acceptance test for the P3.4 raw Simu5G radio exporter."""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

from simu5g_raw_radio_export import export_raw_radio


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    raw_path = Path("p3_4_actual_radio/raw_radio.csv")
    if not raw_path.exists():
        raise FileNotFoundError("Run p3_4_run_recorder.sh before this test")
    with tempfile.TemporaryDirectory(prefix="legra_p3_4_") as temp_dir:
        out_dir = Path(temp_dir)
        counts = export_raw_radio(
            raw_path,
            out_dir,
            slot_duration_ms=1.0,
            snapshot_period_s=0.1,
            rb_budget_ratio=0.5,
            previous_quality=3,
        )
        users = _read(out_dir / "radio_users.csv")
        rbs = _read(out_dir / "radio_rbs.csv")
        metadata = json.loads((out_dir / "export_metadata.json").read_text(encoding="utf-8"))
        assert counts["raw_rows"] == 2004
        assert counts["radio_users"] == 21
        assert counts["radio_rbs"] == 126
        assert all(row["ue_id"] == "ue_2049" for row in users)
        assert all(row["serving_gnb"] == "gnb_1" for row in users)
        assert all(row["total_rbs"] == "6" for row in users)
        assert all(row["rb_available"] == "3" for row in users)
        assert all(row["previous_quality"] == "3" for row in users)
        assert {int(row["rb_index"]) for row in rbs} == set(range(6))
        assert all(float(row["rate_kbps"]) == 1160.0 for row in rbs)
        assert len({(row["timestamp_s"], row["ue_id"], row["rb_index"]) for row in rbs}) == len(rbs)
        assert metadata["rate_source"] == "Simu5G NrAmc::computeBitsPerRbBackground"
        assert metadata["previous_quality_source"] == "explicit_experiment_control_not_video_measurement"
    print("P3.4 PASS: actual Simu5G raw recorder output normalized into complete P3.2 radio tables")


if __name__ == "__main__":
    main()
