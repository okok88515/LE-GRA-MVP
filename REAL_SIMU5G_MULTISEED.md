# Real Simu5G multi-seed protocol

The initial target is 10 explicitly seeded runs for each radio-dispersion
setting (`low`, `mid`, `high`), for 30 independent simulator runs total.

Protocol version 3.0 pins both sources of randomness:

- OMNeT++/INET/Simu5G: `seed-set = SEED`
- SUMO: `<random_number><seed value="SEED"/></random_number>`

The original fixed route and an initial SUMO stochastic-vType attempt were
tested with seeds 1 and 2 and both produced byte-identical mobility. Those
pilot runs are not counted in the dataset. Protocol v3 therefore uses the
versioned `generate_seeded_route.py` helper to draw and write one explicit
desired-speed factor per vehicle from a clipped normal distribution
(`mean=1.0`, `std=0.08`, range `0.85..1.15`). The exact factors are preserved
in `scenario/mobility_seed.json`. The route, vehicle count, departure schedule,
and car-following model remain unchanged. For a given seed, all three radio
dispersions use the same generated mobility input and differ only in power.

Run the full resumable batch from Windows PowerShell:

```powershell
python .\run_real_simu5g_multiseed.py --seeds 1-10
```

Run a pilot or resume a subset:

```powershell
python .\run_real_simu5g_multiseed.py --seeds 1 --dispersions low
python .\run_real_simu5g_multiseed.py --seeds 7-10
```

Outputs are stored by default under WSL at:

```text
/home/opp_env/p3_5_workspace/p3_7_multiseed_v3_outputs/
  low/seed_0001/
  mid/seed_0001/
  high/seed_0001/
  ...
```

Every completed directory contains separate compressed radio/mobility CSVs,
the exact generated scenario, logs, and `run_manifest.json` with seeds,
timestamps, row counts, byte counts, and SHA-256 checksums. A completed run is
never overwritten; rerunning the batch skips it.

The raw CSVs are compressed only after row counts and uncompressed hashes are
recorded. OMNeT++ scalar/vector recording is disabled because the custom raw
CSV recorders are the learner-facing source of truth.
