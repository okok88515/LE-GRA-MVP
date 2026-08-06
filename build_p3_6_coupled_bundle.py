"""Build and validate a P3.6 informative coupled bundle."""

from __future__ import annotations

from build_p3_5_coupled_bundle import build_coupled_bundle


if __name__ == "__main__":
    counts = build_coupled_bundle(
        "p3_6_coupled_output",
        "p3_6_gnbs.csv",
        "p3_6_coupled_bundle",
        previous_quality_mode="deterministic_controller",
    )
    print("P3.6 coupled bundle:")
    for name, value in counts.items():
        print(f"  {name}={value}")
