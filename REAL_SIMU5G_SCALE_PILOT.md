# Real Simu5G scale pilot (research direction 4, phase 1: SUMO network + routes)

Date: 2026-08-27

## Question

`POST_CQI_RESEARCH_ROADMAP_ZH.md` direction 4: every real Simu5G
validation in this project (including direction 2's confirmatory pass) is
fixed at 24 vehicles, a scale carried over from earlier P3.6 scenario
design, not chosen for these experiments. The user's own published paper
uses 50 VU. This phase asks: can the 24-vehicle road network be scaled up
to at least 100 vehicles while preserving vehicle density (area scaled
proportionally to vehicle count, "option B" from the design discussion),
without becoming a hand-tuned, hypothesis-driven redesign?

This is phase 1 only: SUMO-level network and route design, validated with
SUMO alone (no OMNeT++/Simu5G, no RF calibration, no CQI data). Phase 2
(CQI-histogram-only tx-power calibration) and phase 3 (small pilot through
the full OMNeT++/Simu5G pipeline) are not done yet.

## Finding: the original network is algorithmically generated, not hand-authored

`heterogeneous.net.xml`'s header comment records the exact `netgenerate`
invocation used to build it in 2014: a 3x3 grid, 200m spacing (giving the
400x400m network), single lane per edge, static traffic lights at every
junction except the center, which is deliberately unregulated. This means
scaling the network is a matter of re-running the same tool with different
parameters, not hand-editing compiled SUMO XML geometry -- a much lower-risk
path than initially expected.

The original 4 candidate routes (`heterogeneous.rou.xml`) all pass through
the center junction and use only the edges immediately touching it -- the
grid's corner junctions and edges are unused scaffolding. 24 vehicles are
round-robined across the 4 routes with a 0.3s stagger, globally sorted by
depart time (SUMO silently truncates an unsorted route file -- the exact
P3.6 bug `omnetpp.ini`'s header comment already documents avoiding).

## Design: same topology, longer edges

Two ways to enlarge the network were tried:

1. **More grid cells** (`grid.number=5`, same 200m spacing -> 800x800m):
   rejected after testing, because routes then cross 2 additional
   signal-controlled junctions the original design never had (only the
   single center junction is unregulated) -- this changes the qualitative
   route design, not just its scale.
2. **Longer edges, same grid** (`grid.number=3`, `grid.length=400` ->
   800x800m): kept. Same 9-junction topology as the original, same 4
   routes each crossing exactly 2 edges through the single unregulated
   center junction -- zero new signal interactions, a faithful scale-up of
   the exact original design.

```
netgenerate --grid --grid.number=3 --grid.length=400 --tls.unset=B1 \
  --no-turnarounds=true --default.lanenumber=1 \
  --default-junction-type=traffic_light_unregulated \
  --output-file=heterogeneous.net.xml
```

(Junction naming changed between the original SUMO 0.20.0, which used
`row/col` ids like `1/1`, and the current SUMO 1.22.0, which uses
letter+number ids like `B1` -- confirmed by inspection, not guessed; `B1`
is the equivalent center junction for a 3x3 grid.)

100 vehicles (round-robined across the same 4 routes, same 0.3s stagger and
global depart-time sort as the original) were generated as the base
pre-per-seed-patch template.

## A real bug found and fixed: insertion queueing at higher vehicle counts

Headless `sumo` (not the full OMNeT++/Simu5G stack -- cheap, seconds not
minutes) on the first 100-vehicle draft showed only 71-72 of 100 vehicles
ever inserted into the simulation within the 90s window; 28-29 stayed stuck
"waiting." The original 24-vehicle scenario, run through the identical
check, shows zero stuck vehicles.

Root cause: SUMO's default vehicle insertion starts each vehicle from rest
(`departSpeed="0"`). With `accel=0.8 m/s^2`, a vehicle needs about 4 seconds
to open up the `minGap+length=6.5m` gap a follower needs to insert safely --
but the route file staggers same-route departures by only 1.2s (25
vehicles/route at a 0.3s round-robin over 4 routes). Each follower waits on
the one ahead, and the delay compounds across many more vehicles per route
than the original's 6/route, eventually exceeding the fixed 90s window for
a growing tail of vehicles. Confirmed this is scale-driven, not a network
bug, by running the same check against the original file (no queueing) and
against a variant with 2 lanes per edge instead of 1 (no improvement --
confirming lane count wasn't the actual constraint).

Fixed with SUMO's standard technique for this exact situation: `departSpeed="max"
departPos="base"` on every vehicle (insert already at cruising speed rather
than accelerating from a stop). Result: all 100 vehicles insert
successfully (0 waiting), average depart delay drops from ~5s to 0.42s, and
reasoning from the aggregate statistics there is an approximately 30+
second window where all or nearly all 100 vehicles are simultaneously
present in the simulation -- comfortably above the ~15 contiguous seconds
`parse_real_simu5g_data.build_scenarios` needs for full 25-band coverage
across all users.

## What changed vs. the original 24-vehicle scenario

| | Original (validated) | Scale pilot (phase 1 only) |
|---|---|---|
| Network | 3x3 grid, 200m spacing, 400x400m | 3x3 grid, 400m spacing, 800x800m |
| Vehicles | 24 | 100 |
| Route length | ~386m (2 edges) | ~775m (2 edges) |
| gNB positions | (200,80) / (200,320) | (400,160) / (400,640) -- same relative offset, **not yet RF-calibrated** |
| `*.server.numApps` | 24 | 100 |
| Vehicle insertion | default (from rest) | `departSpeed="max" departPos="base"` (needed at this vehicle count) |
| tx power per dispersion | low 30/20dBm, mid 15/10dBm, high 5/0dBm | unchanged (carried over, **not yet validated at this scale**) |

`generate_seeded_route.py`'s hardcoded `len(vehicles) != 24` check was
generalized to accept any non-empty vehicle list, so the existing per-seed
speed-factor patching machinery works unmodified at the new scale.

## Not yet done (phase 2 and beyond)

- **RF/CQI-histogram calibration.** gNB positions and tx power were carried
  over by simple proportional scaling, not validated. Whether 2 gNBs give
  adequate, sensibly-shaped coverage over an 800x800m area is a genuinely
  open question flagged when this direction was scoped -- this phase did
  not touch it. The committed discipline: calibrate by CQI histogram shape
  only, never by looking at grouping-method comparisons, matching
  `p3_7_clean_validation_scenario`'s original methodology.
- **No OMNeT++/Simu5G run yet.** Only headless SUMO (mobility-only) has
  been exercised. The full radio-layer pipeline, `veins_launchd`, and the
  real per-band CQI computation are all still untested at this scale.
- **No seed-runner integration.** `run_p3_7_seed.sh` hardcodes the OMNeT++
  config name `P3_7_Clean_DL`; the new scenario's config is
  `P3_9_Scale_Pilot_DL` (different name, deliberately, to avoid silently
  reusing the P3.7 config for a different scenario). The runner script
  needs a config-name parameter before it can run this scenario.
- **Wall-clock cost at this scale is still unmeasured** -- the original
  aim of doing a cheap pilot before generating any real seed batch.

## Reproduction

Requires the `LE-GRA-opp-env` WSL environment's nix dev shell (`netgenerate`
and `sumo` are provided by a nix-packaged SUMO 1.22.0, not on PATH outside
the shell):

```bash
source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh
printf '<command>\nexit\n' | opp_env shell -w /home/opp_env/p3_5_workspace --no-chdir -q
```

Scenario templates for review: `real_simu5g_data/p3_9_scale_pilot_scenario/{low,mid,high}/`.
Not yet committed -- this is phase 1 of an in-progress direction, pending
phase 2's RF calibration before being treated as validated.
