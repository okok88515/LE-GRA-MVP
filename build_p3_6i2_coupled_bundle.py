"""Build the P3.6i-2 conservative targeted-family coupled bundle."""

from __future__ import annotations

from build_p3_5_coupled_bundle import build_coupled_bundle


if __name__ == "__main__":
    counts = build_coupled_bundle(
        "p3_6i2_coupled_output",
        "p3_6e_gnbs.csv",
        "p3_6i2_coupled_bundle",
        rb_budget_ratio=0.28,
        previous_quality_mode="deterministic_controller_heterogeneous",
    )
    print("P3.6i-2 coupled bundle:")
    for name, value in counts.items():
        print(f"  {name}={value}")
