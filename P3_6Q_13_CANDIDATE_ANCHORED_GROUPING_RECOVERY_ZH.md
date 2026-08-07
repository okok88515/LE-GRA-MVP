# P3.6q-13: candidate-anchored grouping recovers the boundary-shift failure on `q10`

## 背景

`P3.6q-12` 已經把 `q10` 的瓶頸切成兩段：

1. candidate-path recovery
2. final grouping stabilization

在 `p3_6q10_kmeans_candidate_boundary_frontier_275/` 中，我們已經看到：

- learner 的 weak candidate 其實一直都是對的
- `27.6 ~ 28.2` 的 predicted top-k 全部都是 `2|6`
- 但 final grouping 在 `27.7 ~ 28.0` 又 collapse 回 single-group

所以新的問題已經不是：

- 「誰是 weak pair？」

而是：

- 「當 learner 已經知道 weak pair 是 `{ue2, ue6}` 時，如何避免最後 grouping 又退回 single-group？」

## 這輪想法

既然 weak candidate 已經正確，那就不應該再讓 inference path
完全自由地只靠 embedding k-means 重新決定是否 split。

這輪做的最小修正是新增一個 inference-only grouping mode：

- `candidate_anchor_hybrid`

核心想法：

- 先用 weak-score ranking 取 top-k candidate
- 把這些 candidate 直接 anchor 成一個 group
- 剩下的使用 embedding k-means 做 residual partition
- 再把：
  - anchored candidates
  - plain embedding k-means candidates
  一起丟給 DP utility selector 選最好

這不是重新訓練一個新 learner，而是最小的 grouping bridge 修正。

## 實作

新增於：

- `le_gra_mvp.py`

新函式：

- `anchored_candidate_groups(...)`
- `best_candidate_anchor_hybrid_groups(...)`

新 mode：

- `grouping_mode = candidate_anchor_hybrid`

## Focused validation

使用與 `q12` boundary-shift failure 相同的訓練設定，只替換 grouping mode：

- bundle: `p3_6q10_six_user_transition_extension_bundle/bundle`
- train end = `27.5`
- test = `27.6 ~ 28.2`
- supervision:
  - `candidate_membership_weight = 4.0`
  - `pair_sampling = teacher_boundary`
  - `supervision_weight_mode = teacher_candidate_boundary`
  - `frontier_contrast_weight = 6.0`
- grouping mode:
  - `candidate_anchor_hybrid`

Artifacts:

- `p3_6q10_candidate_anchor_hybrid_275/`

## 結果

主結果：

- `Offline teacher = 0.6368533564947124`
- `LE-GRA MVP = 0.6368533564947124`

也就是：

- boundary-shift failure 被完整修回 teacher match

更重要的是 diagnostics：

從 `p3_6q10_candidate_anchor_hybrid_275/teacher_imitation_diagnostics.csv` 可見：

- `27.6 ~ 28.2` 七個 test snapshot
- pairwise / ARI / NMI 全部都是 `1.0`

從 `p3_6q10_candidate_anchor_hybrid_275/weak_group_prediction_audit.csv` 可見：

- predicted top-k 仍然全部都是 `2|6`

這表示：

- weak candidate path 沒有變
- 真正被修好的，是 candidate-to-grouping 的最後一段 transfer

## 這代表什麼？

這輪結果很重要，因為它把 `q10` 的故事再往前推了一步：

### `q11`

告訴我們：

- plain kmeans 失敗於 decoy candidate routing
- membership-aware routing 成功

### `q12`

告訴我們：

- localized joint supervision 可以把 plain learner 的 candidate routing 修回來
- 但 boundary shift 下 final grouping 還是不穩

### `q13`

告訴我們：

- 一旦 candidate routing 已經正確
- 一個很小的 candidate-anchored grouping bridge
- 就足以把 boundary-shift failure 完整修回 teacher

## 新的研究解讀

到這裡，`q10` 已經不再只是「某個 case 成功」而已，
而是形成了一條很完整的機制鏈：

1. teacher side 先提供 sustained dual-weak regime
2. learner side 先用 localized supervision 修回正確 weak candidate
3. inference side 再用 candidate-anchored grouping 防止 split collapse

換句話說，這條線目前最合理的架構性解讀是：

- LE-GRA 在這類 regime 的核心不是單一 embedding clustering
- 而是：
  - weak-candidate discovery
  - candidate-conditioned grouping construction
  兩段式橋接

## 對下一步的建議

最值得做的下一步有兩個：

1. ablation confirmation
   - 驗證 `candidate_anchor_hybrid` 是否只在 frontier-supervised model 上有效
   - 或者只要 candidate path 對了，它就普遍有效

2. report framing
   - `q10 -> q12 -> q13` 已經很適合寫成報告主線：
     - plain clustering fails
     - localized supervision repairs candidate routing
     - candidate-anchored grouping repairs final split transfer

這樣的敘事比單純比較更多 utility 數字，更能說明 LE-GRA 的真正演算法價值。
