# P3.6j-1c Mild Seg_01 Targeted Window Divergence

Last updated: 2026-08-06

## 目標

P3.6j-1b 已經證明一件事：

- family/time-window targeted divergence 確實可以打進 `seg_01`
- 但如果做成過度極化的 `3` 對 `0`，teacher gain 反而下降

所以 P3.6j-1c 的問題很直接：

> 如果把 `seg_01` 的 targeted divergence 改成較溫和的 `2` 對 `1`，
> 能不能保住 original split gain，同時避免 `j-1b` 的反效果？

## 設計

P3.6j-1c 沿用 `p3_6i2` raw trace 與 `rb_budget_ratio = 0.28`，
新增 mode：

- `deterministic_controller_seg01_targeted_mild`

新增 builder：

- `build_p3_6j1c_coupled_bundle.py`

### 定點規則

在 `43.7s ~ 43.9s` 的 `seg_01` 關鍵窗口內：

- 高組 `0,1,15` 維持 `previous_quality = 2`
- 低組 `2,3,4,5` 維持 `previous_quality = 1`

也就是說，這一版的 targeted divergence 是：

- 高組：`2`
- 低組：`1`

比 `j-1b` 的 `3` 對 `0` 更溫和。

## 結果

### 1. mild divergence 成功進入 seg_01

在 `p3_6j1c_coupled_bundle/radio/quality_state.csv` 中，
`43.7s ~ 43.9s` 的關鍵 UE 已經呈現：

- `0,1,15`: `2`
- `2,3,4,5`: `1`

這代表 P3.6j-1c 的 targeted-state 控制有正確生效。

### 2. seg_01 的 previous-quality range = 1

在 `p3_6j1c_teacher_audit/full_bundle/scenario_teacher_decisions.csv` 中：

- `seg_01`: `previous_quality_range = 1`
- `previous_quality_mean = 1.4286`

所以這是一個真正的 family/time-window 定點分歧，但強度比 `j-1b` 小。

### 3. teacher gain 完全回到原始版本

`seg_01` gain：

- `p3_6i2`: `0.057159`
- `p3_6j1b`: `0.028588`
- `p3_6j1c`: `0.057159`

也就是說：

- `j-1b` 把 gain 壓低了
- `j-1c` 又把 gain 拉回原本水準

但 `j-1c` 並沒有進一步超過 `p3_6i2`

### 4. 全域 summary 與 p3_6i2 等價

`full_bundle summary.csv`：

- `positive_gain_count = 9`
- `multi_group_count = 9`
- `max_teacher_gain_vs_single = 0.057159`
- `mean_teacher_gain_vs_single = 0.000292631`

`focus mining`：

- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 7`
- `near_miss_family_count = 13`

這些都與 `p3_6i2` 一致。

## 研究解讀

P3.6j-1c 幫我們補完整個 divergence sweep 的邏輯：

### 過強 divergence：不好

`j-1b` 的 `3` 對 `0` 雖然成功把 `seg_01` 的 `previous_quality_range` 拉到 `3`，
但 teacher gain 幾乎減半。

### 溫和 divergence：不會傷害，但也不會放大

`j-1c` 的 `2` 對 `1` 沒有傷害原本的 split regime，
但也沒有把 teacher gain 往上推。

### 目前最合理的結論

> 單靠 `previous_quality` divergence 的大小本身，
> 似乎不足以放大 `teacher` 與其他方法的差距。

更精準地說：

> 如果 divergence 太強，會傷害 split economics；
> 如果 divergence 太弱或只是溫和，則只會回到原本 regime，
> 不會自動創造更大的 teacher advantage。

## 下一步意義

P3.6j-1、`j-1b`、`j-1c` 三輪合起來，已經把一條研究方向排除得很清楚：

- 不論是全域 quality heterogeneity
- 或 family/time-window targeted quality divergence

單靠 quality-state manipulation 本身，還不足以把 teacher gap 拉大。

因此下一步更值得做的是：

1. `P3.6j-2`
   - 改做 `CQI / resource-cost` 排序錯位
   - 讓 `wideband 相近，但 per-band cost 不同`
2. 或 `P3.6j-2b`
   - 只對被 teacher isolate 的 user 做 cost-side 干預
   - 不再優先從 quality-state 著手

## 一句話總結

P3.6j-1c 的結果說明：

> 適中的 targeted quality divergence 可以保住既有 split regime，
> 但不會額外放大 teacher gain；
> 要真正拉大 teacher、LE-GRA、multi-feature、no-group 的差距，
> 下一步更應該轉向 resource-cost / ambiguity 結構本身。
