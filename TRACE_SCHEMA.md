# LE-GRA Trace Bundle Schema v1

This schema is the boundary between SUMO/Simu5G and the Python LE-GRA learner.
One trace bundle is a directory containing three UTF-8 CSV files. The tables
remain separate so scenario-level values are not duplicated for every UE/RB and
per-RB data can scale independently.

## `scenarios.csv`

One row represents one allocation snapshot for one serving gNB.

| Column | Type | Unit | Required | Intended source |
|---|---|---|---|---|
| `schema_version` | string | - | yes | exporter; currently `1.0` |
| `scenario_id` | string | - | yes | exporter |
| `timestamp_s` | float | s | yes | SUMO/Simu5G |
| `serving_gnb` | string | - | yes | Simu5G |
| `rb_available` | integer | RB | yes | Simu5G scheduler/study load |
| `total_rbs` | integer | RB | yes | Simu5G carrier configuration |
| `dispersion` | string | - | no | legacy synthetic audit label |

The natural snapshot key is `(timestamp_s, serving_gnb)`. `scenario_id` is a
stable, dataset-local identifier for joins.

## `users.csv`

One row represents one UE in one allocation snapshot.

| Column | Type | Unit | Required | Intended source |
|---|---|---|---|---|
| `scenario_id` | string | - | yes | join key |
| `ue_id` | string | - | yes | SUMO vehicle ID |
| `user_index` | integer | - | yes | contiguous `0..N-1` within snapshot |
| `cqi_t_minus_4` ... `cqi_now_raw` | float | CQI index | yes | Simu5G history |
| `cqi_now` | integer | CQI index | yes | rounded scheduling CQI |
| `previous_quality` | integer | representation index | yes | application/QoE state |
| `distance_m` | float | m | yes | SUMO UE/gNB coordinates |
| `speed_mps` | float | m/s | yes | SUMO |
| `direction_to_gnb` | float | cosine-like `[-1,1]` | yes | adapter |
| `x_m`, `y_m` | float | m | no | SUMO |
| `rsrp_dbm`, `rsrq_db`, `wideband_sinr_db` | float | dB/dBm | no | Simu5G |
| `mcs` | integer | index | no | Simu5G |

History rows must use the same physical UE ID across timestamps. A loader may
construct the five CQI lags from earlier snapshots, but the v1 bundle stores the
resolved history explicitly to make training artifacts reproducible.

## `rb_rates.csv`

One row represents one UE/RB observation.

| Column | Type | Unit | Required | Intended source |
|---|---|---|---|---|
| `scenario_id` | string | - | yes | join key |
| `ue_id` | string | - | yes | join key |
| `user_index` | integer | - | yes | matrix row |
| `rb_index` | integer | - | yes | contiguous `0..total_rbs-1` |
| `rate_kbps` | float | kbit/s per RB | yes | adapter/Simu5G |
| `sinr_db` | float | dB | no | Simu5G |
| `cqi` | float | CQI index | no | Simu5G |

`rate_kbps` is the canonical input used by the current allocator. If Simu5G
exports only SINR/CQI, the adapter must record its documented mapping to rate.
Missing optional values are written as empty CSV fields, never fabricated.

## Invariants

1. Every user/RB row references an existing `scenario_id`.
2. `user_index` and `rb_index` are contiguous within each scenario.
3. Every scenario has exactly `N_users * total_rbs` RB rows.
4. `1 <= cqi_now <= 15`, `0 <= previous_quality < 6`.
5. `0 < rb_available <= total_rbs` and all rates are non-negative.
6. Train/test splitting must be trajectory-aware. Adjacent snapshots from the
   same vehicle trajectory must not be randomly split across train and test.
7. Samples from different simulators or measurement campaigns are not merged
   row-wise unless their joint physical relationship is preserved.

## Mapping to `le_gra_mvp.Scenario`

- `users.cqi_*` -> `cqi_history`, `cqi_now`
- `rb_rates.rate_kbps` -> `rb_rates[user_index, rb_index]`
- `scenarios.rb_available` -> `rb_available`
- `users.previous_quality` -> `previous_quality`
- user mobility columns -> `distance`, `speed`, `direction_to_gnb`
- learner `features` are rebuilt after loading via `build_feature_matrix`; they
  are deliberately not serialized as source data.

## P3.0 Acceptance Test

For generated scenarios, the following round trip must pass:

```text
Scenario -> trace bundle -> Scenario
```

All allocation-relevant arrays, offline-teacher partition, and teacher utility
must be identical. This isolates future SUMO/Simu5G integration from learner
and allocator changes.

