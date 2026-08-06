# P3.6m-24：最小版 boundary-aware pair construction v1

日期：2026-08-06

## 這一步為什麼要做

到 `P3.6m-23` 為止，我們已經知道三件事：

1. `boundary-aware replay` 可以救 `m2`
2. 但不能 transfer 到 `m4b`
3. `candidate-conditioned weak-group supervision` 做最小 calibration 後，
   在 `m4b` 上仍然完全不動

所以現在合理的下一步，不是再調一點係數，而是直接改 pair 結構本身。

也就是：

- 不只是「誰的 loss 比較大」
- 而是「哪些 pair 應該被明確拿來教模型」

## 這版的最小想法

目前 `m4b` 的核心錯誤是：

- learner 容易退回 `ue15-only`
- 沒有把 secondary weak candidate `ue4` 拉進來

所以這版我做的最小 pair construction 是：

- 保留 hardest-group supervision
- 但額外把 supervision 壓在最關鍵的局部邊界上

具體來說：

1. 先找 teacher 的 hardest group
2. 在 hardest group 裡，按 mean resource-cost 排前兩名
   - 第一名 = primary weak candidate
   - 第二名 = secondary weak candidate
3. 額外強調：
   - primary ↔ secondary 的正 pair
   - secondary ↔ hardest-group 外部成員的負 pair
   - primary ↔ hardest-group 外部成員維持至少 hardest-group 等級的負 pair

## 程式實作

修改檔案：

- `le_gra_mvp.py`

在 `pairwise_supervision_weights(...)` 新增：

- `teacher_candidate_boundary`

這個新 mode 會：

- 延續 `teacher_hard_group` 的 hardest-group pair weighting
- 再額外對最關鍵的 candidate boundary pairs 加重

這次仍然：

- 不改模型架構
- 不加新 head
- 不改 inference

## focused test

輸出：

- `p3_6m24_m4b_candidate_boundary_pairs_v1/`

測試對象：

- bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
- family: `0|1|15|2|3|4|5 @ gnb_1`
- train window end: `43.6`
- test window: `43.7 ~ 43.9`

保留 replay：

- `boundary_support_start = 43.4`
- `boundary_support_repeat = 16`
- `boundary_support_positive_only = true`

pair 設定：

- `pair_sampling = teacher_boundary`
- `supervision_weight_mode = teacher_candidate_boundary`

這一版刻意不加 candidate membership BCE，避免效果來源混在一起。

## 結果

主結果仍然是：

- `No grouping = 0.547184178084`
- `CQI = 0.579083105194`
- `Resource-cost = 0.579083105194`
- `Multi-feature = 0.579083105194`
- `Teacher = 0.579609048805`
- `LE-GRA = 0.579083105194`

也就是：

- `teacher > LE-GRA = CQI = resource-cost = multi-feature > no-group`

support-side 仍然是完美的：

- `support_pairwise = 1.0`
- `support_ari = 1.0`
- `support_nmi = 1.0`

## 這一步的意義

這一步雖然沒有推動 `m4b`，但研究上其實很重要。

它表示我們現在已經試過三種最小 learner-side hook：

1. replay weighting
2. candidate membership supervision
3. boundary-aware pair construction

而在 `m4b` 上，這三種最小版都還不夠。

## 目前最合理的結論

如果只看 `m4b`，現在已經很難再合理期待：

- 再多一點點 replay
- 再多一點點 candidate BCE
- 再多一點點 pair priority

就會突然把 plateau 打開。

比較像的情況是：

- 這個 regime 需要的是更結構化、而且聯合式的 supervision 設計

例如：

- boundary-aware pair construction + candidate membership 一起用
- 或者直接建立 localized hard negatives，
  明確對比 `{ue15, ue4}` 與 `ue15-only`

## 一句話總結

`P3.6m-24` 證明了：

- 最小版 boundary-aware pair construction 已經實作完成
- 但在 `m4b` 上仍然無法單獨打破 plateau
- 現在若要繼續，就不該再做單一微調，而應該改做結構性的聯合 supervision
