# P3.6 Coupled-Data Audit 基線結果

更新日期：2026-08-06

## 目的

P3.6 的第一步不是擴大 learner 實驗，而是先確認目前的 `p3_5_coupled_bundle/`
到底有沒有足夠的資訊量，能支撐後續 real-trace grouping 研究。

這次新增的 `audit_coupled_trace.py` 會直接針對 coupled bundle 量化：

- active UE / multi-UE snapshots
- CQI saturation
- per-band rate dispersion
- ambiguous-pair ratio
- resource pressure
- handover
- previous-quality distribution 與來源
- join exclusions
- P3.2 join + P3.0 load + offline teacher 是否仍可通過

## 執行方式

```powershell
& C:\Users\Weber\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe `
  -u .\audit_coupled_trace.py
```

輸出目錄：

- `p3_6_coupled_audit/summary.csv`
- `p3_6_coupled_audit/snapshot_metrics.csv`
- `p3_6_coupled_audit/ambiguous_pairs.csv`
- `p3_6_coupled_audit/ue_timeline_metrics.csv`
- `p3_6_coupled_audit/acceptance_gates.csv`

## 核心結果

### 1. 這份 P3.5 bundle 仍然是 integration artifact，不是 learner evidence

Audit 結果很一致，幾乎把 P3.5 的限制全部量化出來了：

| 指標 | 結果 |
|---|---:|
| scenario count | 55 |
| bundle user rows | 59 |
| radio user rows | 67 |
| multi-UE snapshots | 4 |
| CQI unique count | 1 |
| CQI saturation ratio | 1.000000 |
| max per-user profile range | 0.000000 kbps |
| ambiguous pair count | 0 |
| handover count | 0 |
| quality switch count | 0 |
| teacher validation | PASS |

也就是說，目前這份 coupled trace：

1. 幾乎全程只有單一 UE 可用
2. 唯一的 CQI 值就是 15
3. 每個 user 的 25-band profile 完全平坦
4. 沒有任何 ambiguous pairs
5. 沒有 handover
6. `previous_quality` 仍然只是 constant control，不是量測 video state

### 2. 資源壓力雖然存在，但完全沒有變化

`rb_available=12`、`total_rbs=25`，所以：

- resource pressure ratio = `12 / 25 = 0.48`
- min / median / max 全都一樣

這代表目前 bundle 中的 resource pressure 只是固定常數，還沒有形成可研究的負載條件分布。

### 3. Join 與 teacher pipeline 是通的，但資料內容不夠有研究價值

這次 audit 的好消息是：

- P3.2 join 邏輯是通的
- P3.0 bundle loader 是通的
- offline teacher 仍然可跑

壞消息是：

- 通是通了，但資訊量太低
- 現在如果直接拿這份 trace 去看 learner 排名，只會得到誤導性的結果

## Acceptance Gate 結果

`p3_6_coupled_audit/acceptance_gates.csv` 的判定如下：

| Gate | 結果 |
|---|---|
| multi_ue_snapshots_at_least_5 | FAIL |
| cqi_not_fully_saturated | FAIL |
| per_band_dispersion_present | FAIL |
| ambiguous_pairs_present | FAIL |
| measured_previous_quality | FAIL |
| teacher_validation | PASS |

這個 gate 非常重要，因為它清楚表示：

> 現在不能直接進 learner real-trace experiment。

## 目前最合理的 P3.6 下一步

### P3.6a 先把 coupled scenario 做到「有資訊量」

優先目標：

1. 增加 multi-UE overlap，讓同一 snapshot 常態性地有至少 2 個以上 UE。
2. 製造 CQI 不再永遠是 15 的條件。
3. 讓 per-band TBS/rate profile 出現 dispersion，而不是每個 band 都一樣。
4. 讓至少一部分 pair 出現「wideband CQI 相近，但 RB profile 不同」的 ambiguous 情況。
5. 讓 serving gNB 有切換機會，才看得到 handover。

### P3.6b 補 measured video state

目前 `previous_quality_source` 是：

`explicit_experiment_control_not_video_measurement`

這代表目前 quality 只是手動塞進去的常數控制值。下一步應該補：

1. representation / quality index
2. bitrate
3. buffer / playback 相關狀態
4. quality switch event

至少要把 `previous_quality` 變成合理的動態狀態，而不是固定常數。

### P3.6c 每次新 coupled run 都先跑 audit，再決定要不要進 learner

現在 `audit_coupled_trace.py` 已經可以當成標準 gate。正確流程應該是：

1. 生成新的 coupled run
2. 建 bundle
3. 跑 `audit_coupled_trace.py`
4. 看 `acceptance_gates.csv`
5. 只有在關鍵 gate 大多數通過後，才做 learner-focused real-trace experiment

## 一句話結論

P3.6 的 baseline audit 已經完成，而且結論很明確：

> 目前的 P3.5 coupled bundle 證明了整條 SUMO+Veins+Simu5G→join→teacher pipeline 是通的，但它還不具備足夠的 channel ambiguity、resource-pressure variation、handover、或 measured quality state，因此還不能直接拿來當 learner 研究證據。
