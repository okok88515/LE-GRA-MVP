"""Build and validate a P3.6e split-pressure coupled bundle."""

from __future__ import annotations

from build_p3_5_coupled_bundle import build_coupled_bundle


if __name__ == "__main__":
    counts = build_coupled_bundle(
        "p3_6e_coupled_output",
        "p3_6e_gnbs.csv",
        "p3_6e_coupled_bundle",
        previous_quality_mode="deterministic_controller",
    )
    print("P3.6e coupled bundle:")
    for name, value in counts.items():
        print(f"  {name}={value}")
