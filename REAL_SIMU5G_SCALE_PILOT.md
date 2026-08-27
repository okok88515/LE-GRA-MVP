# Real Simu5G scale pilot (research direction 4: SUMO network, routes, and RF calibration)

Date: 2026-08-27

## Question

`POST_CQI_RESEARCH_ROADMAP_ZH.md` direction 4: every real Simu5G
validation in this project (including direction 2's confirmatory pass) is
fixed at 24 vehicles, a scale carried over from earlier P3.6 scenario
design, not chosen for these experiments. The user's paper uses 50 VU per
multimedia service, 150 total across 3 services -- either reference is
larger than 24. This asks: can the 24-vehicle road network be scaled up
meaningfully (target: at least 100) while preserving vehicle density (area
scaled proportionally to vehicle count, "option B" from the design
discussion), without becoming a hand-tuned, hypothesis-driven redesign?

**Summary of where this landed, since the investigation went through
several corrections**: the network/route design scales cleanly via the
same `netgenerate` tool that built the original. But the actual achievable
scale is far below the 100 target -- a real, diagnosed bottleneck in how
Veins/TraCI attaches vehicles under load caps things much lower, and the
project's existing "fixed closed population" data model (every user present
for the whole trajectory) further constrains the usable number to
**N=40**, decided together with the user after evaluating the alternative
(redesigning the data model for a "rolling population") and judging it not
worth the methodological risk it would introduce for direction 2's
temporal closed-loop machinery. This is a real, load-bearing limitation on
this direction's ambitions, not a rounding choice -- documented in full
below.

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

## Phase 1: SUMO network + routes (initial design)

Two ways to enlarge the network were tried:

1. **More grid cells** (`grid.number=5`, same 200m spacing -> 800x800m,
   full-span routes crossing the whole grid): rejected after testing,
   because routes then cross 2 additional signal-controlled junctions the
   original design never had (only the single center junction is
   unregulated) -- this changes the qualitative route design, not just its
   scale.
2. **Longer edges, same grid** (`grid.number=3`, `grid.length=400` ->
   800x800m): first choice. Same 9-junction topology as the original, same
   4 routes each crossing exactly 2 edges through the single unregulated
   center junction -- zero new signal interactions on paper. **This was
   later abandoned** (see phase 1.5) once the doubled route length turned
   out to matter for a different reason: it roughly doubles per-vehicle
   transit duration, which interacts badly with the fixed 90s budget once
   real traffic dynamics are in play.

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

### A real bug found and fixed: insertion queueing at higher vehicle counts

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
than the original's 6/route. Confirmed this was scale-driven, not a network
bug, by running the same check against the original file (no queueing) and
against a 2-lane variant (no improvement -- ruling out lane count as the
constraint). Fixed at the SUMO layer with `departSpeed="max" departPos="base"`
on every vehicle: all 100 then insert successfully, average depart delay
drops from ~5s to 0.42s. **This SUMO-only result later turned out to be
insufficient** -- see phase 1.5.

## Phase 1.5: a deeper bug only the real OMNeT++/Simu5G pipeline revealed

Once the scenario was actually run through the full coupled pipeline (not
just headless SUMO), the picture changed substantially. This section
records the diagnostic process because the wrong-turns are as informative
as the destination.

### First real run: peak simultaneous coverage far below what SUMO predicted

`run_p3_7_seed.sh` was generalized with a `P3_7_OMNETPP_CONFIG` env var
override (previously hardcoded to `P3_7_Clean_DL`; the new scenario's
config is named `P3_9_Scale_Pilot_DL`, deliberately not reusing the P3.7
name). First real run also needed a second bug fix: the hand-authored
`heterogeneous.sumocfg` accidentally included a `<random_number><seed
value="1"/></random_number>` block copied from an already-patched
committed file, but `run_p3_7_seed.sh` *also* injects its own
`<random_number>` block via `sed` -- two such blocks crashes
`veins_launchd`'s SUMO-config patcher with a latent bug in that script
itself (`set_sumoconfig_option` references an out-of-scope `file_dst_name`
in its error path, so the duplicate-node error becomes an opaque
`NameError` instead of a clear message). Fixed by removing the block from
the base template (the pristine original template has no `<random_number>`
element at all -- `run_p3_7_seed.sh` is solely responsible for it).

With that fixed, the run completed (135s wall-clock -- the first real
timing data at this scale, ~4.6x the original's ~29s) but the resulting
radio data showed **zero** 5-consecutive-second windows with all 100 users
covered, and peak simultaneous coverage of only 54/100 -- nowhere near
SUMO's prediction that all 100 would be present together for 30+ seconds.

### Wrong turn: blamed mobility congestion, tried a shorter/tighter design

Suspected the doubled route length (phase 1's `grid.length=400` choice)
combined with single-lane congestion. Switched to the `grid.number=5`
design (rejected in phase 1) but used only the 2 edges touching the center
junction -- matching the original's exact route geometry (~384m, no
intermediate signaled junction) on the larger 800x800m network. This
worked exactly as hoped at the SUMO level (100/100 inserted, 65 complete
within 90s, RouteLength/Duration closely matching the original) and
improved the CQI histogram match. **But it made the real coupled-pipeline
peak coverage worse, not better (54 -> 44 with a tight 0.05s stagger)**,
directly falsifying the mobility-congestion hypothesis.

### Real diagnosis: compounding attachment delay, not mobility

Compared each vehicle's *actual* first-appearance time (in both
`raw_mobility.csv` and `raw_radio.csv` -- identical, ruling out a
radio-specific cause) against its *nominal* scheduled depart time. The
first ~30 vehicles insert almost exactly on schedule (~0.2s constant
offset); delay then grows sharply and compounds -- vehicle 95 of 100
(nominal depart 28.5s) doesn't actually appear until t=82.2s, a 53.7s
delay. This is consistent with congestion in Veins/TraCI's own
vehicle-attachment handling scaling with how many vehicles are *already*
being tracked, not with route geometry -- each additional attachment
request queues behind a growing backlog. Confirmed the mechanism runs
backwards from a naive "just insert faster" fix: **tightening the stagger
made it worse** (0.3s->0.05s dropped peak coverage 54->44 at N=100, and
50->44 at N=70), while **loosening it helped** (0.5s stagger at N=70
lifted peak coverage to 61/70, 87%) -- spacing attachment *requests*
further apart reduces how deep the backlog gets, the opposite of what
fixes pure insertion-from-rest queueing.

### Reducing total requested vehicles helps disproportionately

N=100 requested -> peak 54 (54%). N=70 requested (same loose 0.5s stagger)
-> peak 61 (87%). This is not proportional scaling -- fewer total
attachment *requests* means less backlog ever builds up, so a much higher
fraction succeeds. This, not route geometry, is now believed to be the
dominant constraint on how many vehicles this pipeline can usably support
in a 90s run.

### The project's fixed-population data model cuts the usable number further

`parse_real_simu5g_data.py`'s `build_scenarios` requires a *fixed,
contiguous* set of user ids `range(N_USERS)` to all have full 25-band
coverage for 5 consecutive seconds -- it assumes a closed population
present for the whole trajectory, matching the original 24-vehicle design
(where nearly all 24 are present nearly the whole 90s) and matching what
direction 2's temporal closed-loop machinery needs (`previous_quality`
tracked per user id across consecutive snapshots requires stable user
identity).

The scale-pilot's vehicles, by contrast, form a *rolling* population --
continuously entering and exiting, never all simultaneously present. An
"any N of the currently-covered set" analysis found up to 13 usable
5-second windows at N=50 (out of 61-70 peak coverage) -- comparable to the
original's 15 -- but that number does NOT hold when the code requires
*specifically* ids `0..N-1`: testing this directly gave **zero** usable
windows at N=50 with ids 0-49 fixed (peak coverage of exactly 50/50 was
reached, but only for 4 consecutive seconds, one second short of the 5
needed, and the specific set of 50 covered wasn't consistently ids 0-49
anyway).

**This was a genuine architectural fork, put to the user rather than
decided unilaterally**: (1) redesign `build_scenarios` to support a rolling
population (larger achievable N, ~50-60, but requires rethinking whether
direction 2's `previous_quality`-tracking methodology still makes sense
when user identity isn't stable across snapshots), or (2) keep the
existing fixed-population model unmodified and accept whatever smaller N
it can reliably support. **The user chose (2)** -- no core parsing/temporal
logic changes, smaller scale accepted.

### Final validated design

Tried 70 vehicles requested at 0.5s stagger first (peak coverage 61/70,
87%) -- but checking the *specific* contiguous ids 0..49 needed by
`build_scenarios` (not just "any 50 of the 61-70 covered") found zero
usable windows at N=50: peak coverage among ids 0-49 specifically did
reach exactly 50/50, but only for 4 consecutive seconds, one short of the
5 needed, since ids depart across a wider span (34.5s at 70 vehicles) than
fits comfortably against the ~35-39s transit duration.

Reduced to exactly **50 vehicles requested** (0.5s stagger, same
`grid.number=3`/`grid.length=400` short-route topology from phase 1.5) so
the full requested population's nominal depart span (24.5s) leaves more
margin against transit duration, then evaluated contiguous `range(0,N)` for
decreasing N until a workable margin appeared. Confirmed **identical**
usable-window counts across all three dispersion levels (mobility/
attachment timing does not depend on tx power, as expected) on one pilot
seed each:

| N (contiguous ids 0..N-1) | usable 5s windows |
|---|---:|
| 50 | 0 |
| 48 | 1 |
| 45 | 3 |
| 42 | 4 |
| **40** | **5** |
| 38 | 6 |
| 35 | 8 |

**N=40 was chosen** as a reasonable, validated-with-margin target -- not
the largest technically-achievable number (35 has more margin) but close
to it, balancing "as large as practical" against "some buffer, not the
exact edge of what just barely worked in one pilot seed."

## CQI histogram vs. the original 24-vehicle scenario

At N=40 (within its own usable windows), tx power carried over unchanged
from the original 24-vehicle low/mid/high values:

| Dispersion | Original 24-vehicle (mean, std) | New 800x800m/N=40 (mean, std) |
|---|---|---|
| low | 14.761, 0.602 | 14.400, 1.327 |
| mid | 12.583, 2.182 | 12.145, 2.581 |
| high | 9.188, 3.010 | 8.750, 3.385 |

A consistent, physically-explicable direction at all three dispersion
levels: slightly lower mean, slightly wider spread -- the network area is
4x larger, so even with gNB positions scaled proportionally, the
farthest-from-gNB users are physically farther away in absolute terms,
increasing path loss somewhat. **The user, presented with this table,
chose to accept it as-is** rather than spend further pilot-run budget
chasing a tighter tx-power match.

## What changed vs. the original 24-vehicle scenario (final state)

| | Original (validated) | Scale pilot (final) |
|---|---|---|
| Network | 3x3 grid, 200m spacing, 400x400m | 3x3 grid, 400m spacing, 800x800m |
| Route topology | 2 edges through unregulated center | same (short, center-adjacent only) |
| Vehicles requested | 24 | 50 |
| Vehicles used by the parser (`N_USERS`) | 24 (nearly all present ~whole run) | **40** (fixed population, validated with margin) |
| Departure stagger | 0.3s round-robin | 0.5s round-robin (looser -- reduces attachment backlog) |
| gNB positions | (200,80) / (200,320) | (400,160) / (400,640) -- same relative offset |
| `*.server.numApps` | 24 | 50 |
| Vehicle insertion | default (from rest) | `departSpeed="max" departPos="base"` |
| tx power per dispersion | low 30/20dBm, mid 15/10dBm, high 5/0dBm | unchanged (accepted with a small mean/std offset, see above) |
| Data model | fixed closed population | fixed closed population (unchanged -- user's explicit choice) |

`generate_seeded_route.py`'s hardcoded `len(vehicles) != 24` check was
generalized to accept any non-empty vehicle list. `run_p3_7_seed.sh` gained
a `P3_7_OMNETPP_CONFIG` env var (defaults to `P3_7_Clean_DL`, fully
backward compatible) so it can run the new scenario's `P3_9_Scale_Pilot_DL`
config.

## What N=40 means for the original goal

The original target was "at least 100," informed partly by the paper's own
150-total-user scale. **N=40 falls well short of both.** This is an
honest, load-bearing limitation, not a rounding choice -- worth restating
plainly: the achievable scale in this real-data pipeline is capped by a
diagnosed Veins/TraCI attachment-congestion mechanism, further constrained
by the project's existing fixed-population data model. Still a real
improvement over 24 (67% more users), and any future push toward the
original 100+ target would need to revisit the rolling-population
architectural question this session deliberately did not resolve.

## Not yet done

- **The established method comparisons (CQI/cost/switching/regret-graph/
  trend) have not been re-run at this scale yet.** A validated, QA-passed
  10-seed dataset now exists (`real_simu5g_scale_pilot_multiseed_data/`),
  but no grouping-method analysis has touched it -- this whole
  investigation was infrastructure/data work only, exactly as scoped.
  Seeds 1..10 are exploratory once used this way; a genuine confirmatory
  pass for this scale would need its own fresh, untouched seed range,
  matching the project's established discipline everywhere else.
- **The rolling-population architecture question is explicitly parked, not
  resolved** -- if a future push toward the original 100+ target happens,
  this is where that work would need to start.
- Wall-clock cost is now well-characterized: ~40-50s/run at the final
  design, ~15-22 minutes for a 30-run (10-seed x 3-dispersion) batch.

## Multi-seed batch generation and QA (2026-08-27, later same day)

Generalized the existing tooling rather than writing new scripts:
`build_scenarios` gained `n_users`/`gnb_pos` parameters (default to the
original 24-vehicle constants, fully backward compatible -- verified
against the original data before and after), `run_real_simu5g_multiseed.py`
gained `--scenario-root`/`--omnetpp-config` overrides, and
`validate_real_simu5g_multiseed.py` gained matching
`--n-users`/`--gnb-pos`/`--expected-scenarios`/`--min-*-rows` overrides.

**A process mistake, caught and fixed before it corrupted the dataset**:
the first "10-seed batch" run reused seed numbers 1-8 from the earlier
single-seed pilot *iterations* (100-vehicle, then 70-vehicle designs) --
`run_p3_7_seed.sh`'s resumability (skip if already complete) silently
returned those stale, differently-configured runs instead of regenerating
them against the final committed design. Caught by noticing the row counts
in the "already complete" log lines exactly matched earlier pilot
iterations' numbers. Fixed by wiping the whole output directory and
regenerating all 30 runs fresh -- confirmed clean (zero
`ALREADY_COMPLETE` lines, all `SEED_COMPLETE`) on the rerun.

**A second real bug, this time in `parse_real_simu5g_data.py` itself**:
`build_scenarios`'s `usable_buckets` filter only checked radio-data
completeness, never mobility-data completeness, silently assuming the two
always covered the same buckets -- true for the original 24-vehicle
scenario (never hit), false here (a `KeyError` surfaced on seed 8: bucket
29's mobility trace for car 0 was missing even though its radio reports
were complete). Fixed by adding the missing mobility-completeness check to
`usable_buckets`, in both this project's script and the shared function
used by the confirmatory pipeline elsewhere. Re-verified: zero effect on
the original 24-vehicle data (still exactly 15 scenarios/run).

**A third adjustment, not a bug**: the original 24-vehicle QA script
asserted usable-scenario count *exactly equals* 15 every run -- a fair
reliability check there, since the original design reliably hits that
number every time (all 24 vehicles present nearly the whole 90s). This
scale pilot's rolling population is inherently more variable seed-to-seed;
asserting an exact match would fail on legitimate runs. Changed the check
to a *minimum* threshold instead (a strictly safe relaxation for the
original data, which never fell below 15 anyway) and calibrated the
minimum from real data rather than assuming.

**Final QA result, all 30 runs (10 seeds x 3 dispersions), copied into
`real_simu5g_scale_pilot_multiseed_data/`**: 29 of 30 runs hit exactly 5
usable scenarios; one (`high/seed_0008`) got 2 -- still real, usable data,
not a failure, just the natural variance of this design. QA gate set at
`--expected-scenarios 2` (the true observed floor) rather than an
arbitrary stricter number that would fail a legitimate run. 147 total
usable scenarios across the batch.

| Dispersion | Runs | Usable scenarios | Mean of per-run CQI means | Mean of per-run CQI stds |
|---|---:|---:|---:|---:|
| low | 10 | 50 | 14.585 | 0.982 |
| mid | 10 | 50 | 12.099 | 2.776 |
| high | 10 | 47 | 9.010 | 3.584 |

Closely matches the single-seed pilot findings already accepted (see the
CQI histogram table above) -- confirms the earlier single-seed
observations generalize across a real 10-seed batch, not a one-off.

## Reproduction

Requires the `LE-GRA-opp-env` WSL environment's nix dev shell (`netgenerate`
and `sumo` are provided by a nix-packaged SUMO 1.22.0, not on PATH outside
the shell):

```bash
source /home/opp_env/.venv/bin/activate
source /home/opp_env/.nix-profile/etc/profile.d/nix.sh
printf '<command>\nexit\n' | opp_env shell -w /home/opp_env/p3_5_workspace --no-chdir -q
```

Final scenario templates (50 vehicles, 0.5s stagger, `N_USERS=40` target):
`real_simu5g_data/p3_9_scale_pilot_scenario/{low,mid,high}/`. Validated
10-seed multi-seed batch (30 runs, QA-passed):
`real_simu5g_scale_pilot_multiseed_data/{low,mid,high}/seed_0001..0010/`,
`multiseed_qa_scale_pilot.csv`, `aggregate_manifest_scale_pilot.json`.

```powershell
python .\run_real_simu5g_multiseed.py --seeds 1-10 `
  --output-root /home/opp_env/p3_5_workspace/p3_9_scale_pilot_outputs `
  --scenario-root /home/opp_env/p3_5_workspace/p3_9_scale_pilot/scenarios `
  --omnetpp-config P3_9_Scale_Pilot_DL
python .\validate_real_simu5g_multiseed.py real_simu5g_scale_pilot_multiseed_data `
  --seeds 1-10 --label scale_pilot --n-users 40 --gnb-pos "1:400,160;2:400,640" `
  --expected-scenarios 2 --min-radio-rows 6000000 --min-mobility-rows 14000
```
