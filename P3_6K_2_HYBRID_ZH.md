# P3.6k-2 Hybrid Tail-Window Redesign

Last updated: 2026-08-06

## 結論先講

`P3.6k-2` 是目前最重要的一次突破。

我們第一次在**新的 family** 上，成功讓 teacher 穩定開始分群，而且不是靠舊的
`seg_01` plateau family。

新的正增益 family 是：

- `3|4|5|6 @ gnb_2`

新的正增益 window 是：

- `29.2s ~ 29.9s`

teacher 穩定分成：

- `[[0,1,3],[2]]`

也就是把：

- `ue 5`

單獨切出去。

## 背景

`P3.6k-1` 已經告訴我們：

- `3|4|5|6 @ gnb_2` 整段都是 near-miss
- 後段 `29.2s ~ 29.9s` 的 `ue 5` 已經有明顯的低 CQI / 高 cost
- 但 teacher 還是不分群

而且單做 localized previous-quality divergence 的 probe 也失敗了。

因此 `P3.6k-2` 改成測：

> 不是只補 quality-side  
> 而是讓 `ue 5` 的尾段 cost-side 與 quality-side 一起對齊

## 設計

新增 builder：

- `build_p3_6k2_hybrid_bundle.py`

輸出：

- `p3_6k2_hybrid_bundle/`

### 目標 family

- `3|4|5|6 @ gnb_2`

### 目標時間窗

- `29.2s ~ 29.9s`

### 設計內容

#### 1. `ue 5` strong cost-side penalty

`ue 5` 的 per-band `rb_rates` 在尾段被壓低：

- `>=1128 kbps` 乘上 `0.84`
- `>=984 kbps` 乘上 `0.80`
- 其餘乘上 `0.90`

#### 2. localized previous-quality divergence

在同一段尾窗：

- `ue 5 -> previous_quality = 0`
- `ue 3 -> previous_quality = 2`
- `ue 4 -> previous_quality = 2`
- `ue 6 -> previous_quality = 2`

這樣做的用意是：

- `ue 5` 同時在 throughput/cost 與 quality-history 上都變成弱候選者
- 其餘三人則形成穩定主群

## 正式結果

### Teacher audit

執行：

```powershell
python run_p3_6_teacher_decision_audit.py --bundle-dir p3_6k2_hybrid_bundle/bundle --out-dir p3_6k2_teacher_audit
```

`summary.csv`：

- `scenario_count = 830`
- `multi_group_count = 17`
- `positive_gain_count = 17`
- `mean_teacher_gain_vs_single = 0.0006647611833829516`
- `max_teacher_gain_vs_single = 0.05715940214371462`

和 base `p3_6i2` 比較：

- `multi_group_count: 9 -> 17`
- `positive_gain_count: 9 -> 17`

這代表這次不是只改一條 family 的局部現象，而是全 bundle 的 teacher 正增益 snapshot 總數也被拉高了。

### Focus mining

執行：

```powershell
python mine_focus_slices.py --audit-csv p3_6k2_teacher_audit/full_bundle/scenario_teacher_decisions.csv --out-dir p3_6k2_focus_mining
```

`summary.txt`：

- `positive_segment_count = 3`
- `candidate_temporal_slice_count = 14`
- `near_miss_family_count = 12`

這裡也很重要，因為：

- 原本只有 `2` 個 positive segments
- 現在變成 `3` 個

也就是說，我們真的新增出了一條新的正增益 segment。

## 新增的 positive segment

`positive_segments.csv` 顯示新的 segment 是：

- `seg_03`
- family: `3|4|5|6 @ gnb_2`
- time: `29.2s ~ 29.9s`
- snapshot_count: `8`
- mean_gain_vs_single: `0.038608503577`
- max_gain_vs_single: `0.038608503577`

這是目前最重要的成果。

## 逐時間窗結果

在 `3|4|5|6 @ gnb_2` 上：

### `28.8s ~ 29.1s`

- teacher 仍是單群 `[[0,1,2,3]]`
- `teacher_gain_vs_single = 0.0`

### `29.2s ~ 29.9s`

- teacher 穩定變成 `[[0,1,3],[2]]`
- `teacher_gain_vs_single = 0.038608503576809006`

也就是：

- 前段仍是 near-miss
- 一過 `29.2s`，這條 family 就跨過 split threshold

這是一個非常乾淨的 temporal onset。

## 為什麼這次成功

這次成功的核心，不是單純把某個 user 變得更慘，而是：

> `ue 5` 的弱化第一次同時在  
> `cost-side` 與 `previous-quality-side` 兩個維度上對齊

從正式 audit 可以看到：

- `previous_quality_range = 2`
- `resource_cost_range = 1.166667 ~ 1.333333`
- `cqi_range = 4 ~ 6`

這比 `k-1` base 的尾段明顯更完整：

- 以前只有 CQI / cost 在拉開
- 現在 quality-history 也一起拉開

所以 teacher 終於有足夠理由把 `ue 5` 切出去。

## 與舊 regime 的差別

### 舊 `seg_01`

- 是 `gnb_1`
- 有 plateau 問題
- 很容易在微調時 collapse
- 更像「局部 temporal flip 問題」

### 新 `seg_03`

- 是 `gnb_2`
- 不是 plateau 微調
- 是一條原本 near-miss、後來成功跨過 threshold 的新 family
- 更像「tail-window onset split」

這代表研究故事開始變得更完整：

我們現在不只知道怎麼在舊 family 上摸 plateau，
也知道怎麼在新 family 上**創造新的正增益 split regime**。

## 研究意義

`P3.6k-2` 目前至少帶來三個重要進展：

### 1. 新 family 成功

這是第一條不是 `seg_01` 的新正增益 family。

### 2. hybrid 比單邊 redesign 有效

- pure quality-side 失敗
- pure cost-side 在這條 family 上原本也不夠
- hybrid 對齊之後成功

### 3. teacher 需要的是「對齊的弱訊號」

不是訊號越大越好，而是：

- cost 弱化
- quality-history 弱化

要對齊到同一個 user、同一段時間窗，teacher 才會真的想分。

## 下一步建議

最合理的下一步有兩條。

### 路線 A：先跑 learner

這是我目前最推薦的。

理由：

- 我們已經有新的正增益 segment `seg_03`
- 長度有 `8` 個 snapshots
- gain 也不低 (`0.0386`)
- 而且 family 結構比舊 `seg_01` 更乾淨

這很適合拿來做：

- focused temporal learner
- `teacher / LE-GRA / multi-feature / no-group` 比較

### 路線 B：擴 family

如果你想先把 teacher regime 再擴大，可以做：

- 以 `31|4|5|6 @ gnb_2` 為 follow-up
- 看看它是不是 `3|4|5|6` 的延伸變體

但我會覺得先跑 learner 比較划算，因為現在終於有新 regime 了。

## 一句話結論

`P3.6k-2` 是目前最重要的實驗突破：我們成功在新的 family `3|4|5|6 @ gnb_2` 上，用 tail-window cost+quality hybrid redesign，創造出一條新的 8-snapshot 正增益 teacher split segment。
