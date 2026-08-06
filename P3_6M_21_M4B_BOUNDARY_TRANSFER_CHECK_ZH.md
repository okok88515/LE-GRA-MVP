# P3.6m-21：boundary-aware replay 對 m4b 的 transfer check

日期：2026-08-06

## 為什麼這一步值得做

`P3.6m-19` 和 `P3.6m-20` 已經證明：

- 在 `m2` 上
- 最小版 `boundary-aware support weighting`
- 不是假訊號，而且在 `43.8 / 43.9` 上很穩

但我們還不能因此直接宣稱：

- 這已經解掉整個 dual-weak 問題

因為最關鍵的外部驗證還沒做：

- 同一個 family 裡，另一個真正困難、而且之前一直卡住的 `m4b`
- 能不能也靠同一套最小 replay protocol 被救起來？

這一步就是在回答這個問題。

## 測試對象

bundle：

- `p3_6m4b_threshold_nudge_bundle/bundle`

核心 regime：

- family: `0|1|15|2|3|4|5 @ gnb_1`
- `43.7s ~ 43.9s` 是真正的 dual-weak evaluation window
- `43.6s` 是 threshold-bridge snapshot

這個 regime 的已知難點是：

- teacher 會做 dual-weak split
- learner 和強 baseline 會一起退回舊的 `ue15`-only 解

也就是說，它正好是拿來測 replay transfer 的最好地方。

## 實驗設定

這次我刻意不重新調參，直接把在 `m2` 上最成功的最小 protocol 原封不動搬過來：

- `boundary_support_start = 43.4`
- `boundary_support_repeat = 16`
- `boundary_support_positive_only = true`

其他設定維持 focused learner 主流程：

- `train_window_end = 43.6`
- `test_window = 43.7 ~ 43.9`
- `restart_seeds = 7 9 11`
- `background_train_limit = 150`

輸出：

- `p3_6m21_m4b_boundary_weighting_transfer_r16/`

## 結果

### 主比較結果

- `No grouping = 0.547184178084`
- `CQI = 0.579083105194`
- `Resource-cost = 0.579083105194`
- `Multi-feature = 0.579083105194`
- `Offline teacher = 0.579609048805`
- `LE-GRA = 0.579083105194`

也就是：

- `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`

完全沒有動。

### support-side 結果

這次最值得注意的不是主結果，而是 support-side 已經非常漂亮：

- `boundary_support_selected_scenarios = 1`
- `effective_boundary_support_scenarios = 15`
- `support_selection_pairwise_accuracy = 1.0`
- `support_selection_ari = 1.0`
- `support_selection_nmi = 1.0`
- `support_selection_utility_gap = 0.0`

換句話說：

- replay 的確有吃進去
- support-side imitation 也已經變成 perfect

但最後：

- `selected_restart_seed = 9`
- holdout utility 完全沒動

## 這一步最重要的研究意義

這個結果非常關鍵，因為它幫我們把「boundary replay 的有效範圍」劃得更清楚了。

### 1. `m2` 的成功是真的，不是噪音

因為我們已經在 `m2` 上看到：

- repeat sweep 有明確 threshold 現象
- robustness check 也成立

所以 `m2` 的成功仍然是有效結論。

### 2. 但 replay-only 不是同 family 的通用解

這次在 `m4b` 上失敗，而且失敗得很乾淨：

- support-side 已經 perfect
- 但 holdout 還是 stuck

所以現在不能再把問題簡化成：

- 「只要把 late boundary support replay 多一點就好」

因為如果真的是這麼單純，`m4b` 應該也要一起被救起來。

### 3. 現在的 bottleneck 更像是「secondary weak candidate 的顯式建模還不夠」

從目前 evidence 看起來：

- `m2` 對 replay 比較敏感，可能只需要把 boundary-positive support density 補足
- `m4b` 則更頑固，代表它不是純粹的 support density 問題

比較像是 learner 仍然缺：

- 對 secondary weak candidate（這裡是 `ue4`）的顯式辨識壓力
- 或者缺少直接把 `{ue15, ue4}` 和舊的 `ue15`-only split 分開的 supervision

## 目前的停損點

我認為這一步已經足夠構成一個很合理的 stop-loss：

- `boundary-aware support weighting` 值得保留
- 但不要再繼續靠 replay-only 做更多 sweep

因為我們已經看到：

- 它能救 `m2`
- 但不能自動轉移到 `m4b`

再繼續只調 replay 強度，資訊增益會開始變小。

## 建議的下一步

下一步最值得做的，不是再回去調 selector，也不是擴大實驗，而是做下一層 learner-side refinement：

1. boundary-aware pair construction  
   直接在 secondary weak candidate 周圍造更有針對性的 pair。

2. candidate-conditioned weak-group supervision  
   不只教「有弱組」，而是更明確教 learner 哪個候選要被拉進弱組。

3. localized hard negatives  
   直接把：
   - 正確的 `{ue15, ue4}`
   - 錯誤的 `ue15-only`
   這兩種 grouping 拉開。

## 一句話總結

`P3.6m-21` 給出的最重要結論是：

- 最小版 boundary replay 已經證明能救 `m2`
- 但它無法直接 transfer 到更頑固的 `m4b`
- 所以下一階段不能再只靠 replay，必須進入更明確的 secondary-weak-candidate supervision
