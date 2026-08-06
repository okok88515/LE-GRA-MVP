# P3.6 Coupled Data Audit

更新日期：2026-08-06

## 目的

P3.6 的任務不是先擴大 learner 實驗，而是先回答一個更根本的問題：

`p3_5_coupled_bundle/` 這批 SUMO + Veins + Simu5G trace，到底有沒有足夠的資訊量，值得拿來做真實 trace 的 grouping 研究？

因此我們先對 coupled bundle 做 audit，量化：

- multi-UE snapshot 數量
- CQI 是否過度飽和
- per-band rate / TBS 是否有 dispersion
- ambiguous pair 是否存在
- resource pressure 是否固定
- handover 是否真的出現
- previous quality 是否是量測值，還是只是實驗控制值
- P3.2 join、P3.0 bundle loader、offline teacher 是否仍然可用

## 本次資料來源

本次 audit 使用新的 informative coupled scenario：

- 目錄：`p3_6_coupled_output/`
- bundle：`p3_6_coupled_bundle/`
- audit 輸出：`p3_6_coupled_audit/`

核心流程：

1. `p3_5_apply_recorders.sh`
2. `p3_6_run_informative_coupled.sh`
3. `build_p3_6_coupled_bundle.py`
4. `audit_coupled_trace.py --bundle-dir ./p3_6_coupled_bundle --out-dir ./p3_6_coupled_audit`

## 主要結果

### Bundle 規模

| 指標 | 數值 |
|---|---:|
| scenario count | 657 |
| bundle user rows | 2463 |
| bundle rb rows | 61575 |
| mobility scenario rows | 662 |
| mobility user rows | 2503 |
| radio user rows | 2503 |
| radio rb rows | 62575 |
| join retention ratio | 0.984019 |

### Snapshot 與負載

| 指標 | 數值 |
|---|---:|
| active UEs min | 1 |
| active UEs median | 3 |
| active UEs max | 7 |
| multi-UE snapshot count | 614 |
| serving gNB unique count | 2 |
| resource pressure ratio | 0.48 |

解讀：

- 這次已經不再是只有 1 個 UE 的 smoke artifact。
- 大多數 snapshot 都有多個 UE，可支撐 grouping 問題。
- 兩個 gNB 都有實際參與 serving。
- `rb_available=12`、`total_rbs=25`，所以目前 resource pressure 固定在 `0.48`。

### CQI 與 per-band profile

| 指標 | 數值 |
|---|---:|
| CQI unique values | 12, 13, 14, 15 |
| CQI min | 12 |
| CQI median | 15 |
| CQI max | 15 |
| CQI saturation ratio | 0.712140 |
| per-user profile range mean | 252.657734 kbps |
| per-user profile range max | 856.000000 kbps |
| per-user profile std mean | 61.951113 kbps |

解讀：

- CQI 不再是全域 `15`，代表 trace 終於脫離完全飽和。
- 但 CQI 仍偏高，說明目前場景仍是「高 CQI、但不完全平坦」。
- `max profile range = 856 kbps` 很關鍵，代表同一個 user 的 25-band profile 已經明顯不平。
- 這正是 LE-GRA 想利用的資訊：wideband CQI 類似，不代表 RB profile 也一樣。

### Ambiguity 與 handover

| 指標 | 數值 |
|---|---:|
| pair count | 4640 |
| ambiguous pair count | 1944 |
| ambiguous pair ratio | 0.418966 |
| handover count | 4 |
| handover UE count | 4 |

解讀：

- `ambiguous_pair_count = 1944` 是這次最重要的正面訊號。
- 代表資料中確實存在大量「CQI 很像，但 RB profile 不同」的 user pair。
- 這正是 CQI-only baseline 容易失效、而 LE-GRA 有機會展現價值的情境。
- `handover_count = 4` 代表 coupled trace 已經不再是單一 serving-cell 的靜態資料。

### previous quality 狀態

| 指標 | 數值 |
|---|---:|
| previous quality unique values | 3 |
| quality switch count | 0 |
| previous quality source | explicit_experiment_control_not_video_measurement |

解讀：

- 這一項仍然沒有過關。
- `previous_quality` 目前仍是實驗控制值，不是真正由 video adaptation、buffer 或 bitrate history 推出的量測狀態。
- 所以 P3.6 雖然已經完成 coupled trace 的 channel / mobility / handover 面，但還沒有完成 quality-state 面。

## Acceptance Gates

`p3_6_coupled_audit/acceptance_gates.csv` 的結果如下：

| Gate | 結果 |
|---|---|
| multi_ue_snapshots_at_least_5 | PASS |
| cqi_not_fully_saturated | PASS |
| per_band_dispersion_present | PASS |
| ambiguous_pairs_present | PASS |
| measured_previous_quality | FAIL |
| teacher_validation | PASS |

## 目前結論

這次 P3.6 的結論和先前完全不同：

> 新的 informative coupled scenario 已經成功產生可研究的 coupled trace。  
> 它具備多 UE、非完全飽和 CQI、明顯 per-band dispersion、ambiguous pair，以及實際 handover。  
> 因此它已經足以支撐「為什麼 CQI-only 不夠、為什麼 LE-GRA 有價值」這條研究主線。  
> 唯一還沒過關的缺口，是 measured previous quality。

## 下一步

建議下一步聚焦在 P3.6b，而不是立刻擴大 learner matrix：

1. 定義 coupled trace 的 quality-state schema
2. 讓 `previous_quality` 來自可辯護的量測或模擬狀態，而不是固定控制值
3. 重跑 `p3_6_run_informative_coupled.sh`
4. 重建 bundle 與 audit
5. 等 `measured_previous_quality` gate 通過後，再進 learner 實驗
