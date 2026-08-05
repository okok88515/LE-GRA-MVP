# P3.2 Simu5G Radio Export Schema

Simu5G/OMNeT++ normally records time-series vectors in `.vec` and summary
results in `.sca`. P3.2 defines two normalized CSV tables that can be produced
by a custom Simu5G recorder or by post-processing selected OMNeT++ vectors.

## `radio_users.csv`

One row per UE and radio reporting instant.

| Column | Type | Unit | Required |
|---|---|---|---|
| `timestamp_s` | float | s | yes |
| `ue_id` | string | - | yes |
| `serving_gnb` | string | - | yes |
| `wideband_cqi` | float | CQI index | yes |
| `previous_quality` | integer | representation index | yes |
| `total_rbs` | integer | RB | yes |
| `rb_available` | integer | RB | yes |
| `wideband_sinr_db` | float | dB | no |
| `rsrp_dbm` | float | dBm | no |
| `rsrq_db` | float | dB | no |
| `mcs` | integer | index | no |

`rb_available` is the study allocation budget visible to LE-GRA, not silently
the number of RBs already assigned to that UE. Its exact Simu5G source or
experimental control rule must be documented.

## `radio_rbs.csv`

One row per UE, reporting instant, and RB/subband.

| Column | Type | Unit | Required |
|---|---|---|---|
| `timestamp_s` | float | s | yes |
| `ue_id` | string | - | yes |
| `serving_gnb` | string | - | yes |
| `rb_index` | integer | - | yes |
| `rate_kbps` | float | kbit/s per RB | yes |
| `sinr_db` | float | dB | no |
| `cqi` | float | CQI index | no |

If the simulator exposes bands rather than physical RBs, `rb_index` denotes a
documented logical subband and `total_rbs` must use the same abstraction. Rate
must be the achievable payload rate under the chosen MCS/BLER/overhead model.

## Join rules

1. Join mobility and radio on exact `(timestamp_s, ue_id)` in schema v1.
2. Simu5G `serving_gnb` overrides P3.1 nearest-gNB assignment.
3. All UEs in `(timestamp_s, serving_gnb)` must agree on `total_rbs` and
   `rb_available`.
4. Every retained UE must have exactly `total_rbs` contiguous RB rows.
5. Five chronologically ordered wideband CQIs form `cqi_history`; warm-up rows
   without enough history are excluded from the final bundle.
6. Stable SUMO and Simu5G UE IDs are mandatory. A mapping table is required if
   module paths and vehicle IDs differ.
7. Missing required physical data causes rejection, never random imputation.

