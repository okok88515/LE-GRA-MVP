# P3.6j-1 Quality-Divergence Variant

Last updated: 2026-08-06

## 目標

P3.6j-1 的任務是先做最小風險版本的 scenario redesign：

- 不改 `p3_6i2` 的 traffic interaction
- 不重做 mobility / route 結構
- 只透過 deterministic quality-state controller 放大 `previous_quality` 分歧

原本的假設是：

> 如果同一個 informative family 裡的使用者帶著更大的 previous-quality 差異進入 split regime，
> teacher 對 single-group 的 QoE 懲罰可能會更明顯，
> 進而拉大 `teacher` 與 `no-group` / `multi-feature` 的差距。

## 實作內容

### 1. 新增 controller mode

在 `simu5g_raw_radio_export.py` 新增：

- `deterministic_controller_family_divergence`

這個 mode 不改 raw radio，也不改 SUMO/Simu5G 軌跡，只改 `previous_quality` 的生成機制。

### 2. 設計三種 profile

#### High-anchor

適用 UE：

- `0`
- `1`
- `15`
- `31`

特性：

- 較高 initial quality
- 較高 initial buffer
- 較容易升品質
- 有較高品質下界

#### Low-anchor

適用 UE：

- `2`
- `3`
- `4`
- `5`
- `6`
- `7`

特性：

- 較低 initial quality
- 較低 initial buffer
- 較難升品質
- 有較低品質上界

#### Bridge

其他 UE 使用中間型 profile，避免全系統只剩二元極端。

### 3. 品質帶約束

第二版 j-1 不是只靠不同 EWMA / buffer profile，而是再加入明確的品質帶：

- `high_anchor`: quality bound `[2, 5]`
- `low_anchor`: quality bound `[0, 1]`
- `bridge`: quality bound `[1, 3]`

這樣做的目的是避免 controller 在關鍵窗口重新收斂成同一層品質。

### 4. 新增 bundle builder

新增：

- `build_p3_6j1_coupled_bundle.py`

它沿用 `p3_6i2_coupled_output/` 的 raw trace，輸出：

- `p3_6j1_coupled_bundle/`

因此 P3.6j-1 是在固定 mobility / radio trace 上純測試 quality-state redesign 的效果。

## 執行結果

### Bundle

`build_p3_6j1_coupled_bundle.py` 成功完成：

- `teacher_scenarios = 875`
- retained UE IDs 與 `p3_6i2` 相同
- raw trace / radio rows / mobility rows 都與 `p3_6i2` 一致

這代表本輪沒有破壞既有 informative interaction 結構。

### Global quality divergence 確實被放大

在 `p3_6j1_coupled_bundle/radio/quality_state.csv` 中，關鍵 UE 的整體分布有明顯拉開：

- `0`: mean `2.105`, range `1~5`
- `15`: mean `2.189`, range `1~3`
- `31`: mean `2.482`, range `2~3`
- `2`: mean `1.266`, range `0~2`
- `3`: mean `1.295`, range `0~2`
- `4`: mean `1.260`, range `0~2`
- `5`: mean `1.293`, range `0~2`

所以從全域統計來看，j-1 controller 的確成功把高需求群與低需求群拉開。

## Teacher audit 結果

`p3_6j1_teacher_audit/full_bundle/summary.csv` 與 `p3_6i2` 完全相同：

- `positive_gain_count = 9`
- `multi_group_count = 9`
- `max_teacher_gain_vs_single = 0.057159`
- `mean_teacher_gain_vs_single = 0.000292631`

`p3_6j1_focus_mining/summary.txt` 也與 `p3_6i2` 相同：

- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 7`
- `near_miss_family_count = 13`

目前 recovered positive segments 仍然是：

1. `0|1|15|2|3|4|5 @ gnb_1`
2. `0|1|2|3|4 @ gnb_2`

## 最重要的發現

雖然全域 quality divergence 被拉開了，但在真正最關鍵的 positive-gain family 上，
`previous_quality` 仍然幾乎沒變。

### seg_01 family

`0|1|15|2|3|4|5 @ gnb_1` 在 `43.7s ~ 43.9s`：

- `previous_quality_range = 0`
- `previous_quality_mean = 1.0`

也就是說，這一段 family 在 teacher 真正會 split 的時間窗內，所有人最後仍然收斂到同一個品質層級。

### seg_02 family

`0|1|2|3|4 @ gnb_2` 在 `18.7s ~ 19.2s`：

- `previous_quality_range = 1`
- `previous_quality_mean = 1.4`

這表示分歧有一點點進入 family，但仍不足以改變 teacher 的整體 decision summary。

## 結論

P3.6j-1 已經完成，而且給了我們一個很重要的負結果：

> 單純放大全域 `previous_quality` 分歧，不會自動轉成更大的 teacher gain。

原因不是 controller 沒生效，而是：

> 真正影響 teacher 的不是「整體資料集平均上有沒有分歧」，
> 而是「在 teacher 會 split 的那個 family、那個時間窗內，分歧有沒有真的存在並持續」。

這個發現很有價值，因為它把下一步方向收斂得更明確：

- P3.6j-2 不應該只是再把全域 profile 拉更開
- 下一步應改成 **family/time-window targeted quality divergence**

## 建議的下一步

最合理的後續不是回頭大改 learner，而是進一個更精準的 `j-1b / j-2`：

1. 只針對 `seg_01` / `seg_02` 的 active family 做 quality-state targeting
2. 讓分歧在關鍵時間窗內被「鎖住」，而不是在進入 regime 前就重新收斂
3. 優先攻擊 `seg_01`
   - 因為它的 teacher gain 更大
   - 目前卻完全沒有 previous-quality range

## 目前最精準的研究解讀

P3.6j-1 的結果不是失敗，而是把問題定義得更精準：

> 如果想拉大 `teacher` 與其他方法的差距，真正需要的是
> 「在關鍵 family / 關鍵時間窗內的 targeted state divergence」，
> 而不是全域平均意義上的 quality heterogeneity。
