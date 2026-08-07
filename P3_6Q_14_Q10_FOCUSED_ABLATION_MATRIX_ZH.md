# P3.6q-14: q10 focused ablation matrix shows the real gain is conditional, not universal

## 背景

`P3.6q-13` 一開始看起來像是很強的結論：

- `candidate_anchor_hybrid` 可以把 `q10` shifted-boundary failure 直接修回 teacher match

但在把實驗拆成同 seed 比較之後，我們發現原本的 unrestricted restart 結果有一個重要混淆：

- plain `candidate_anchor_hybrid` 的成功，部分其實只是因為它最後選到了比較好的 restart seed
- 不是單看 grouping mode 就一定會成功

所以這一輪的重點不是再追新 tweak，而是先把 `q10` 的解釋變乾淨。

## Focused matrix

固定 regime：

- bundle: `p3_6q10_six_user_transition_extension_bundle/bundle`
- focus UEs: `1|2|3|4|5|6`
- train end = `27.5`
- test = `27.6 ~ 28.2`
- `max_groups = 3`

比較兩個軸：

1. training supervision
   - plain
   - localized supervision
2. grouping mode
   - `kmeans_embedding`
   - `candidate_anchor_hybrid`

並且補成同 seed 檢查：

- seed 9
- seed 11

結果表：

| Supervision | Grouping mode | Restart seed | LE-GRA utility | Teacher utility | Gap |
|---|---|---:|---:|---:|---:|
| plain | `kmeans_embedding` | 9 | 0.6186 | 0.6369 | 0.0182 |
| plain | `candidate_anchor_hybrid` | 9 | 0.6186 | 0.6369 | 0.0182 |
| plain | `kmeans_embedding` | 11 | 0.6369 | 0.6369 | 0.0000 |
| plain | `candidate_anchor_hybrid` | 11 | 0.6369 | 0.6369 | 0.0000 |
| localized | `kmeans_embedding` | 9 | 0.6186 | 0.6369 | 0.0182 |
| localized | `candidate_anchor_hybrid` | 9 | 0.6369 | 0.6369 | 0.0000 |
| localized | `kmeans_embedding` | 11 | 0.6369 | 0.6369 | 0.0000 |
| localized | `candidate_anchor_hybrid` | 11 | 0.6369 | 0.6369 | 0.0000 |

Artifacts:

- `p3_6q10_focused_ablation_matrix.csv`
- `p3_6q10_plain_baseline_275/`
- `p3_6q10_candidate_anchor_plain_275_seed9/`
- `p3_6q10_plain_baseline_275_seed11/`
- `p3_6q10_candidate_anchor_plain_275_seed11/`
- `p3_6q10_kmeans_candidate_boundary_frontier_275/`
- `p3_6q10_candidate_anchor_hybrid_275/`
- `p3_6q10_kmeans_candidate_boundary_frontier_275_seed11/`
- `p3_6q10_candidate_anchor_hybrid_275_seed11/`

## 最重要發現

### 1. `candidate_anchor_hybrid` 不是無條件增益

在 seed 9：

- plain `kmeans_embedding` 失敗
- plain `candidate_anchor_hybrid` 也失敗

也就是說：

- 如果沒有先把 learner 帶到對的局部表示，單靠 anchored grouping 並不會自動救回 `q10`

### 2. `candidate_anchor_hybrid` 的價值是修補特定失敗路徑

在 seed 9 + localized supervision：

- `kmeans_embedding` 還是失敗
- `candidate_anchor_hybrid` 則回到 full teacher match

這說明它真正修補的是：

- candidate 已經被 localized supervision 推到比較對的區域後
- plain final grouping 仍然會 collapse 的那一條路徑

換句話說，它的角色比較像：

- conditional grouping bridge

而不是：

- universal grouping replacement

### 3. seed 11 本來就是容易成功的 basin

不管是：

- plain / localized
- `kmeans_embedding` / `candidate_anchor_hybrid`

只要固定在 seed 11，四個設定都能達到 teacher match。

這代表：

- `q10` 的困難性不是所有 optimization basin 都一樣
- 至少存在一個本來就會收斂到正確雙群 split 的 basin

### 4. `q13` 仍然成立，但要改寫得更精確

`q13` 原本的大方向沒有錯：

- 在失敗的 shifted-boundary path 上，candidate-anchored grouping 確實能把結果修回來

但更精確的表述應該是：

- `candidate_anchor_hybrid` fixes the failing localized-supervision + seed-9 path
- it is not evidence that anchored grouping universally dominates plain k-means

## 目前最準確的機制理解

`q10` 現在比較像一個「兩層條件式 bottleneck」：

1. optimization / representation basin
   - 不同 restart seed 會進到不同 basin
2. final group-construction path
   - 在某些 basin 中，就算 candidate path 已經接近 teacher，plain grouping 還是可能 collapse

所以目前最合理的說法是：

- localized supervision 幫忙把 learner 推向比較有機會成功的局部結構
- `candidate_anchor_hybrid` 進一步修補其中仍會 collapse 的 final grouping path
- 但如果本來就落在好的 basin，plain `kmeans_embedding` 也能成功

## 對研究敘事的影響

這個結果其實是好事，因為它把故事從「某個小 tweak 突然神奇地全解」修正成比較可信的研究論點：

- `q10` 已經證明 LE-GRA 的失敗不是單一原因
- 問題同時包含：
  - training-side basin sensitivity
  - inference-side grouping construction sensitivity

這也讓後面的研究方向更清楚：

- 不要再把所有成功都粗暴歸功於某一個 local tweak
- 要開始把「成功 basin」和「失敗 basin」分開分析

## 下一步建議

最值得做的不是再加更多小 tweak，而是做更有辨識力的兩條線：

1. basin diagnostics
   - 系統化比較 seed 9 和 seed 11 的 support-train / focus-test candidate path、embedding geometry、split evidence
   - 目標是回答：為什麼 seed 11 本來就能成功，而 seed 9 需要 bridge
2. robustness expansion under controlled seeds
   - 固定 seed 9 去看 `candidate_anchor_hybrid` 的修補是否能 transfer 到鄰近 boundary slice
   - 固定 seed 11 去確認它是不是 stable easy basin，而不是單點 luck

如果只選一條先做，我會優先做：

- seed 9 vs seed 11 的 basin diagnostics

因為這會決定我們接下來該把重心放在：

- 更好的 supervision / optimization
- 還是更好的 inference-time grouping construction
