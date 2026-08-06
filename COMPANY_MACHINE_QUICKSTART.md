# Company Machine Quickstart

Last updated: 2026-08-06

This note is the practical day-to-day checklist for using the company machine
as the P3.5/P3.6 coupled-simulation workstation.

## What is already installed

The machine now has a working dedicated WSL distro:

- distro name: `LE-GRA-opp-env`

Inside that distro, the verified P3.5 workspace is installed at:

- `/home/opp_env/p3_5_workspace`

Verified components:

- `OMNeT++ 6.3.0`
- `INET 4.6.0`
- `Veins 5.3.1`
- `Simu5G 1.4.3`
- `SUMO 1.22.0`

Important: this official `opp_env` image mounts the Windows drive at
`/c/...`, not the more common `/mnt/c/...`.

For this repo, use:

- Windows path: `C:\Users\Weber\Documents\LE-GRA-MVP`
- WSL path: `/c/Users/Weber/Documents/LE-GRA-MVP`

## Quick checks

### 1. Verify the simulator environment

Run:

```powershell
wsl -d LE-GRA-opp-env -- bash --noprofile --norc -lc "cd /c/Users/Weber/Documents/LE-GRA-MVP && tr -d '\r' < p3_5_check_environment.sh | bash"
```

Success signal:

```text
P3_5_ENVIRONMENT_OK
```

### 2. Verify the committed coupled bundle

Run:

```powershell
& C:\Users\Weber\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -u .\run_p3_5_coupled_test.py
```

Success signal:

```text
P3.5 PASS: one-clock SUMO+Veins+Simu5G run...
```

### 3. Verify the current coupled-data audit baseline

Run:

```powershell
& C:\Users\Weber\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -u .\audit_coupled_trace.py
```

Main outputs:

- `p3_6_coupled_audit/summary.csv`
- `p3_6_coupled_audit/acceptance_gates.csv`
- `p3_6_coupled_audit/snapshot_metrics.csv`

## Most common commands

### Enter the WSL distro

```powershell
wsl -d LE-GRA-opp-env
```

### Apply the P3.5 recorders

```powershell
wsl -d LE-GRA-opp-env -- bash --noprofile --norc -lc "cd /c/Users/Weber/Documents/LE-GRA-MVP && tr -d '\r' < p3_5_apply_recorders.sh | bash"
```

### Run the P3.5 coupled smoke scenario

```powershell
wsl -d LE-GRA-opp-env -- bash --noprofile --norc -lc "cd /c/Users/Weber/Documents/LE-GRA-MVP && tr -d '\r' < p3_5_run_coupled_smoke.sh | bash"
```

### Rebuild the normalized P3.5 bundle from raw outputs

```powershell
& C:\Users\Weber\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -u .\build_p3_5_coupled_bundle.py
```

### Re-run the P3.6 coupled-data audit

```powershell
& C:\Users\Weber\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -u .\audit_coupled_trace.py
```

## Recommended working order

When you start a new company-machine session, use this order:

1. Run the environment check until `P3_5_ENVIRONMENT_OK`.
2. Run `run_p3_5_coupled_test.py` until `P3.5 PASS`.
3. If you changed the scenario or recorder, rerun the coupled smoke script.
4. Rebuild the bundle with `build_p3_5_coupled_bundle.py`.
5. Run `audit_coupled_trace.py`.
6. Read `p3_6_coupled_audit/acceptance_gates.csv`.
7. Only if the key P3.6 gates are satisfied should you move on to learner-facing
   real-trace experiments.

## Current research reality

As of 2026-08-06, the committed `p3_5_coupled_bundle/` is a valid integration
artifact, but not yet a learner-quality dataset.

The current coupled audit baseline shows:

- too few multi-UE snapshots,
- fully saturated CQI,
- zero per-band profile dispersion,
- zero ambiguous pairs,
- zero handovers,
- `previous_quality` still controlled rather than measured.

This means the next priority is still:

- P3.6a: build a more informative coupled scenario
- P3.6b: record measured video/application quality state

Not yet:

- larger learner matrix,
- larger seed sweep,
- larger `Kmax` study.

## Read these first

If you need the research context rather than just the commands, start with:

- `SESSION_HANDOFF.md`
- `P3_5_SUMO_SIMU5G_COUPLING_ZH.md`
- `P3_6_NEXT_STEPS_ZH.md`
- `P3_6_COUPLED_AUDIT_ZH.md`
