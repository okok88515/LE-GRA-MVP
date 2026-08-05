# P3.1 SUMO Mobility Staging Schema

P3.1 consumes SUMO Floating Car Data (FCD) XML and produces two staging CSVs.
These files are intentionally not a complete P3.0 trace bundle: CQI, radio
rates, RB budget, and application state must be added by P3.2 Simu5G rather
than fabricated by the mobility adapter.

## Input: SUMO FCD XML

Enable SUMO FCD output with an `.sumocfg` output option such as:

```xml
<output>
    <fcd-output value="mobility.fcd.xml"/>
</output>
```

Required vehicle attributes are `id`, `x`, `y`, `angle`, and `speed`. The
adapter preserves optional `lane`, `pos`, `slope`, and `type` values when
available.

## Input: `gnbs.csv`

| Column | Type | Unit | Description |
|---|---|---|---|
| `gnb_id` | string | - | unique serving-gNB identifier |
| `x_m` | float | m | gNB x in the same SUMO Cartesian coordinate system |
| `y_m` | float | m | gNB y in the same SUMO Cartesian coordinate system |

Do not mix GPS longitude/latitude with SUMO Cartesian coordinates without an
explicit projection transform.

## Output: `sumo_scenarios.csv`

| Column | Description |
|---|---|
| `mobility_schema_version` | currently `1.0` |
| `scenario_id` | stable snapshot identifier |
| `timestamp_s` | SUMO simulation time |
| `serving_gnb` | nearest configured gNB |
| `user_count` | UEs assigned to the gNB at that time |

## Output: `sumo_mobility.csv`

| Column | Unit | Description |
|---|---|---|
| `scenario_id` | - | snapshot join key |
| `timestamp_s` | s | SUMO simulation time |
| `serving_gnb` | - | nearest gNB |
| `ue_id` | - | stable SUMO vehicle ID |
| `user_index` | - | contiguous within scenario |
| `trajectory_step` | - | observation index for this UE |
| `x_m`, `y_m` | m | SUMO Cartesian position |
| `speed_mps` | m/s | SUMO speed |
| `angle_deg` | degree | SUMO navigation angle |
| `distance_m` | m | Euclidean UE-to-gNB distance |
| `direction_to_gnb` | `[-1,1]` | cosine between velocity and UE-to-gNB vectors |
| `lane_id`, `lane_position_m`, `slope_deg`, `vehicle_type` | mixed | optional FCD metadata |

SUMO navigation angle uses 0 degrees for north/+y and 90 degrees for east/+x.
The adapter therefore computes the unit heading as
`(sin(angle), cos(angle))`. At zero speed or zero distance,
`direction_to_gnb` is defined as 0.

## Snapshot rules

1. Each `(timestamp_s, nearest_gnb)` pair is one candidate snapshot.
2. `--min-users` removes undersized snapshots; default is 1 for lossless export.
3. `--max-users` deterministically retains the closest UEs and then orders
   selected UEs by `ue_id`; default 0 means no cap.
4. UE IDs remain stable across time; `user_index` is snapshot-local only.
5. P3.2 must join Simu5G radio output by timestamp, gNB, and UE ID before
   creating the required P3.0 `scenarios/users/rb_rates` bundle.

