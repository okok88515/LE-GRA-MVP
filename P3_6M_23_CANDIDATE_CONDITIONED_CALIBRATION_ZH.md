# P3.6m-23：candidate-conditioned weak-group supervision 的最小 calibration

日期：2026-08-06

## 這一步要回答的問題

`P3.6m-22` 已經把最小版
`candidate-conditioned weak-group supervision`
接進 learner 流程了。

但第一版在 `m4b` 上沒有推動結果。

所以這一步要確認一件很直接的事：

- 是不是只是因為 v1 的權重太保守？

如果只是太小，那我們只要小幅把強度拉高，理論上應該至少看到一些門檻反應。

## 固定條件

這次我刻意不再碰其他變數，全部固定在 `P3.6m-22` 的設定：

- bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
- family: `0|1|15|2|3|4|5 @ gnb_1`
- train end: `43.6`
- test: `43.7 ~ 43.9`
- boundary replay:
  - `boundary_support_start = 43.4`
  - `boundary_support_repeat = 16`
  - `boundary_support_positive_only = true`
- candidate top-k:
  - `candidate_top_k = 2`

只掃兩個強度參數：

- `candidate_membership_weight`
- `candidate_secondary_scale`

## 2x2 calibration

四組如下：

1. `w2_s2`
2. `w4_s2`
3. `w2_s4`
4. `w4_s4`

輸出：

- `p3_6m23_m4b_candidate_calib_w2_s2/`
- `p3_6m23_m4b_candidate_calib_w4_s2/`
- `p3_6m23_m4b_candidate_calib_w2_s4/`
- `p3_6m23_m4b_candidate_calib_w4_s4/`

## 結果

四組結果完全一樣。

每一組都是：

- selected restart seed = `9`
- `support_pairwise = 1.0`
- `teacher = 0.579609048805`
- `CQI = 0.579083105194`
- `LE-GRA = 0.579083105194`

也就是：

- `teacher > LE-GRA = CQI`

而且不是「改善很小」，而是：

- 完全沒有動

## 這個結果代表什麼

這一步最大的價值就是幫我們很乾淨地停損。

### 1. 問題不是單純的係數太小

如果 `P3.6m-22` 只是因為：

- `candidate_membership_weight` 太小
- 或 `secondary_scale` 太小

那這裡至少應該看到某一格開始有一點反應。

但現在四格全都不動，表示：

- 問題不是純粹的 coefficient calibration

### 2. candidate-membership-BCE-only 這條支線先到這裡

這不代表 candidate supervision 方向錯。

比較準確的說法是：

- 「只靠 sparse candidate BCE，再把係數調大」
- 還不足以改變 `m4b` 的錯誤解

換句話說，現在缺的不是更多同一種壓力，而是不同結構的壓力。

### 3. support-side 已經不是現在的主問題

所有這些 run 都還是：

- `support_pairwise = 1.0`

所以我們可以更有把握地說：

- 現在不是 support imitation 做不好
- 而是 learner 在最後那個 dual-weak decision boundary 上，
  仍然缺少真正能把 `{ue15, ue4}` 和 `ue15-only` 分開的 supervision 結構

## 目前的停損點

我認為這一步已經足夠構成很合理的 stop-loss：

- 不要再花時間做 candidate BCE 的小幅調參

因為我們已經試過：

- 加大整體 candidate loss
- 加大 secondary candidate 權重

都沒有任何反應。

## 建議下一步

下一步最值得做的是結構性地改 supervision，而不是再調係數。

最合理的方向有兩個：

1. boundary-aware pair construction  
   直接在 secondary weak candidate 周邊建立更有針對性的 pair。

2. localized hard negatives  
   明確把：
   - 正確的 `{ue15, ue4}`
   - 錯誤的 `ue15-only`
   這兩種 grouping 拉開。

## 一句話總結

`P3.6m-23` 證明了：

- 最小版 `candidate-conditioned weak-group supervision` 的第一輪 calibration
  在 `m4b` 上完全沒有門檻反應
- 所以現在應該停止做 weight-only tuning，改做更結構化的 secondary-candidate supervision
