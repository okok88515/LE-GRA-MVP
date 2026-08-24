# Real Simu5G data completion status

Last checked: 2026-08-24

## What is present

- Three committed mobility exports (`raw`, `mid`, `high`), but all three are
  byte-identical and therefore represent one mobility trajectory.
- `real_validation_results.csv`, containing 15 usable adjacent snapshots per
  dispersion/load cell.
- Power-setting configs and `run_p3_7.sh` documenting the original run.

## Recovery completed on 2026-08-24

The three files referenced by `parse_real_simu5g_data.py` were reconstructed
with OMNeT++ 6.3.0, INET 4.6.0, Simu5G 1.4.3, and Veins 5.3.1 and restored to
the Windows workspace:

- `real_simu5g_data/raw_radio.csv`
- `real_simu5g_data/mid_raw_radio.csv`
- `real_simu5g_data/high_raw_radio.csv`

The recovery rebuilt the P3.7 scenario from the committed P3.7 configs and
route, the P3.6 launch/SUMO config, and Simu5G's original NR cars SUMO network
assets.  Existing recorder hooks and compiled libraries were verified before
the runs.  Full hashes and row counts are recorded in
`real_simu5g_data/recovery_manifest.json`.

All three datasets parse to 15 complete scenarios with 24 users, 25 bands,
and five CQI history steps.  Re-running `run_real_data_validation.py` produced
the committed `real_validation_results.csv` exactly (no content diff).

## Remaining work before real data can be confirmatory

1. Run low/mid/high radio settings under at least 10 independent simulation
   seeds; 20 seeds is the target for a confirmatory dataset.
2. Preserve each run separately.  Do not concatenate adjacent snapshots and
   treat them as independent runs.
3. Record native wideband CQI if available, per-band CQI/rate, stable UE IDs,
   and the actual previous application quality instead of forcing it to zero.
4. Create a run-level manifest containing simulator versions, configs, seed,
   route file hash, power settings, logger patch hash, and raw-file checksums.
5. Split or bootstrap at the run/trajectory level.

Changing transmit power affects both mean channel quality and its spread.
Accordingly, the eventual QA report must show CQI mean, standard deviation,
and quantiles; the labels low/mid/high cannot be accepted from config names
alone.

The raw-data reproducibility blocker is resolved.  Statistical independence,
actual previous-quality state, and multi-run sample size remain limitations.
