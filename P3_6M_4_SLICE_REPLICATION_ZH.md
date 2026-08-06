# P3.6m-4 slice replication around the positive-family decoy regime

## 目的

`P3.6m-3` 已經證明：

- 在 `43.8s ~ 43.9s`
- `teacher > LE-GRA = multi-feature`
- 而且差距來自 split identity，不是 split 數量

但當時的 test set 只有 2 個 snapshot。  
`P3.6m-4` 的目標就是把這條 evidence 擴成更多相似 slice。

## P3.6m-4a: decoy-only sweep

新腳本：

- `run_p3_6m4_positive_slice_sweep.py`

輸出：

- `p3_6m4_slice_sweep/`

這一輪 sweep 掃的是：

- 更早的 decoy 啟動時間
- 更強一點的 `ue4` rate penalty
- 更深一點的 `ue4` history drop

測試變體共 6 個：

- `baseline_m2_like`
- `start_43_3_same`
- `start_43_2_same`
- `start_43_4_medium`
- `start_43_3_medium`
- `start_43_4_stronger`

### decoy-only sweep 結果

來自 `p3_6m4_slice_sweep/variant_summary.csv`：

- 所有變體都一樣
  - `positive_gain_count = 3`
  - `positive_dualweak_count = 3`
  - `first_positive_time_s = 43.7`

也就是說：

- 不管 decoy 多早開始
- 不管 `ue4` decoy 稍微強一點還是弱一點
- dual-weak 正增益段都沒有從 `43.7~43.9` 往前擴

最重要的結論是：

- 單靠 `ue4 decoy` 不足以把 regime 門檻往前推
- 真正的 threshold 還是在 `ue15` 身上

## P3.6m-4b: primary-weak threshold nudge

既然 sweep 顯示 bottleneck 在 `ue15`，就直接做更精準的 `threshold nudge`。

新 builder：

- `build_p3_6m4b_threshold_nudge_bundle.py`

輸出：

- `p3_6m4b_threshold_nudge_bundle/`
- `p3_6m4b_teacher_audit/`
- `p3_6m4b_family_focus/`
- `p3_6m4b_focus_mining/`

### 設計

起點：

- `p3_6m2_positive_family_decoy_bundle`

只改一個點：

- family: `0|1|15|2|3|4|5 @ gnb_1`
- timestamp: `43.6s`
- 只動 `ue 15`

改動內容：

- 對 `ue15` 的 RB rate 做更強的 penalty
- 把 `ue15 cqi_now_raw` 再往下壓 `4.0`
- 讓 `ue15` 在 `43.6s` 更接近 `43.7s` 那個已知正增益 threshold

## P3.6m-4b teacher 結果

來自 `p3_6m4b_teacher_audit/full_bundle/scenario_teacher_decisions.csv`：

- `43.4s ~ 43.5s`
  - 仍然 single-group
- `43.6s`
  - split 出現
  - `teacher_groups = [[0,1,3,4,5,6],[2]]`
  - `teacher_gain_vs_single = 0.031898927110`
- `43.7s ~ 43.9s`
  - 保持 `P3.6m-2` 的 dual-weak split
  - `teacher_groups = [[0,1,3,4,6],[2,5]]`
  - `teacher_gain_vs_single = 0.032424870721`

### 新的 positive segment

來自 `p3_6m4b_focus_mining/positive_segments.csv`：

- `seg_01 = 0|1|15|2|3|4|5 @ gnb_1`
- `43.6s ~ 43.9s`
- `snapshot_count = 4`
- `mean_gain_vs_single = 0.032293384818`

所以 `m-4b` 成功把正增益 segment 從：

- 原本 `43.7s ~ 43.9s` 的 3 個 snapshot

擴成：

- `43.6s ~ 43.9s` 的 4 個 snapshot

## 這次擴張代表什麼

### 1. 正增益 evidence 變長了

這次確實不是只有單點成功，而是把正增益段往前擴了一步。

### 2. `43.6s` 是過渡點，不是完整 dual-weak 點

要很小心的是：

- `43.6s` 的 split 還是舊的單弱者型態
  - 弱組只有 `{ue15}`
- `43.7s ~ 43.9s` 才是新的 dual-weak 型態
  - 弱組是 `{ue15, ue4}`

所以 `43.6s` 比較像：

- 把這條 segment 往前接長的 threshold-bridge snapshot

而不是：

- 完整複製出新的 dual-weak ambiguity snapshot

## P3.6m-4 focused learner

既然 `43.6` 現在成了新 bridge point，最合理的 learner protocol 是：

- train 到 `43.6s`
- test 看 `43.7s ~ 43.9s`

新輸出：

- `p3_6m4b_seg01_split436_temporal_learner/`

### split summary

- `focus_test_scenarios = 3`
- `focus_test_positive_gain_count = 3`
- `train_window_end = 43.6`
- `test_window = 43.7s ~ 43.9s`

也就是說：

- 現在 test set 從原本 `2` 個 dual-weak snapshot
- 擴成 `3` 個 dual-weak snapshot

### main comparison

和 `m-3` 一樣，結果仍然是：

- `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`

數值：

- `Offline teacher = 0.579609048805`
- `LE-GRA MVP = 0.579083105194`
- `Multi-feature = 0.579083105194`
- `No grouping = 0.547184178084`

### imitation diagnostics

3 個 test snapshot 全部一致：

- `pairwise_accuracy = 0.714285714286`
- `ARI = 0.416666666667`
- `NMI = 0.428140178120`

所以 `m-4` 的最大價值不是把差距變大，而是把原本只有 2 個 snapshot 的 learner-side evidence，
擴成了 3 個連續 dual-weak snapshot，讓結論更穩。

## 結論

`P3.6m-4` 的結論可以分成兩層：

### 第一層

decoy-only sweep 失敗，證明：

- 這條 family 的真正 threshold 不在 `ue4`
- 而是在 `ue15`

### 第二層

`m-4b` 成功把正增益 segment 往前延長到 `43.6s`，並讓：

- focused learner test set
  - 從 `2` 個 dual-weak snapshot
  - 擴成 `3` 個 dual-weak snapshot

而且核心 learner-side separation 仍然成立：

- `teacher` 會把 `{ue15, ue4}` 放在弱組
- `LE-GRA / multi-feature` 仍然只 isolate `ue15`

## 下一步建議

下一步最合理的是進 `P3.6m-5`：

1. 不是再花很多時間硬擴 `43.5`
2. 而是把目前已經穩定的 `43.7~43.9` dual-weak regime 當作主要訓練／驗證 slice
3. 開始做 learner-side supervision redesign

因為現在最重要的 bottleneck 已經不是：

- 能不能做出分歧

而是：

- 能不能讓 `LE-GRA` 學會把 `ue4` 也拉進弱組，真正超過 `multi-feature`
