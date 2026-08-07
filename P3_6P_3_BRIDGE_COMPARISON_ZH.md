# P3.6p-3 Bridge Comparison Matrix (ZH)

日期：2026-08-07

## 目的

把目前最重要的 learner-side inference bridge 結論整理成一份可直接交接的比較表，避免後續又回到「到底是 supervision 不夠，還是 bridge 沒把修好的訊號顯露出來」這個老問題。

這份比較表的用途不是宣稱所有列都是完全同條件控制實驗，而是把目前已經驗證過的關鍵 regime 放在同一張圖上，看出：

1. 哪些 regime 舊 `kmeans_embedding` 本來就能過
2. 哪些 regime 一定需要更好的 inference bridge
3. `hybrid_membership_kmeans` 目前是否已經足夠強，值得升級成預設路徑

## 先講一句結論

目前最重要的結論很清楚：

- `m2` 是「easy / already-solvable」regime
- `m4b` 是「bridge-needed」regime
- `o8 @ 18.7s` 則是最乾淨的單點 probe，直接證明舊 `kmeans_embedding` 會 collapse，但 `membership_order` 與 `hybrid_membership_kmeans` 都能補回 teacher

也就是說，現在的主要瓶頸已經不再是「再加更多小 supervision tweak」；而是要決定：

- 是否把 `hybrid_membership_kmeans` 升級成 LE-GRA 的預設 inference path

## Comparison matrix

詳見：

- `p3_6p3_bridge_comparison_matrix.csv`

高層摘要如下。

### 1. `o8 @ 18.7s`：bridge failure 的最乾淨單點證據

- teacher utility：`0.6198214236671593`
- `kmeans_embedding` LE-GRA：`0.6071841780840183`
- `membership_order` LE-GRA：`0.6198214236671593`
- `hybrid_membership_kmeans` LE-GRA：`0.6198214236671593`

關鍵解讀：

- top-k weak pair 訊號其實已經指到正確的 `{ue3, ue4}`
- 舊 `kmeans_embedding` 不是「找到錯的 split」
- 它是最後在 candidate-to-final grouping 這一步直接 collapse 成 single-group
- 所以這裡真正壞掉的是 bridge，不是 weak-pair evidence 本身

### 2. `m4b`：train-side 修好之後，bridge 決定你能不能真的追上 teacher

- teacher utility：`0.5796090488051922`
- localized-hard-negative + 舊 `kmeans_embedding` LE-GRA：`0.5790831051936908`
- localized-hard-negative + `membership_order` LE-GRA：`0.5796090488051922`
- localized-hard-negative + `hybrid_membership_kmeans` LE-GRA：`0.5796090488051922`

關鍵解讀：

- `m4b` 不是純粹 train-side 無解
- train-side supervision 已經把 frontier 修到夠好了
- 真正決定能不能跨過最後那條線的，是 inference bridge 能不能把 `{ue15, ue4}` 這個 weak group 從 candidate 變成 final grouping

### 3. `m2`：不是新的 learner-hard regime，而是 already-solvable sibling

- teacher utility：`0.5796090488051922`
- 舊 focused `kmeans_embedding` LE-GRA：`0.5790831051936908`
- localized-hard-negative + `membership_order` LE-GRA：`0.5796090488051922`
- localized-hard-negative + `hybrid_membership_kmeans` LE-GRA：`0.5796090488051922`

這裡要很誠實地註記：

- `m2` 這一列不是「完全同條件 bridge-only A/B」
- 因為目前留下來可直接引用的 `kmeans_embedding` focused run，來自較早的 focused learner protocol
- 但它已經足夠支持我們現在真正需要的判斷：
  - `m2` 不是像 `m4b` 那樣一定要靠新 bridge 才能救回來的 regime
  - 它本來就比較接近 already-solvable 類型

## 目前最重要的研究判斷

可以把目前 family / regime 分成兩類：

### A. already-solvable

代表例：

- `m2`
- `n3`

特徵：

- 舊 `kmeans_embedding` 就已經能接近或直接追上 teacher
- 新 bridge 不會害它退化，但也不是成功的必要條件

### B. bridge-needed

代表例：

- `m4b`
- `o8 @ 18.7s`

特徵：

- weak signal 或 frontier 已經開始對了
- 但舊 bridge 會在最後一步把可用 candidate 壓扁成較差 grouping
- `membership_order` 或 `hybrid_membership_kmeans` 才能把這個訊號真正轉成 teacher-level utility

## 補充驗證：`n3` hybrid sanity check 已完成

為了避免太早把 `hybrid_membership_kmeans` 升成預設 bridge，我們又做了一次最小 sanity check：

- run:
  - `p3_6p4_n3_hybrid_sanity/`
- protocol:
  - same focused `n3` window
  - `joint_supervision_mode = none`
  - only changed `grouping_mode = hybrid_membership_kmeans`

結果：

- `Offline teacher = 0.4603881335630136`
- `LE-GRA MVP = 0.4603881335630136`
- mean pairwise / ARI / NMI:
  - all `1.0`

這代表：

- hybrid bridge 不只在 `m4b` / `o8` 這些 bridge-needed regime 能補洞
- 在 `n3` 這種 already-solvable regime 上也沒有造成退化
- 所以把 hybrid bridge 當成下一階段的候選預設路徑，現在有更好的正面證據支持

## 對專案方向的意義

這個比較表帶來兩個很實際的結論。

### 結論 1：不要再把所有失敗都怪到 learner supervision

在 `o8` 和 `m4b` 上，我們已經有直接證據表明：

- learner 並不是完全沒學到
- 真正的問題常常是最後的 candidate-to-grouping bridge

### 結論 2：下一步最值得投資的不是更多局部 loss tweak，而是 default bridge 決策

現在最值得做的下一步不是再回去掃：

- replay-only 小變體
- candidate BCE 權重微調
- pair priority 小修

而是做一件更乾淨的事：

1. 以 `hybrid_membership_kmeans` 當成候選預設路徑
2. 在已知的 focused regimes 上做最小驗證
3. 確認它是否在 easy regimes 不退化、在 hard regimes 穩定補洞

## 建議下一步

最合理的下一步順序：

1. 把 `hybrid_membership_kmeans` 視為「候選預設 inference bridge」
2. 在 `n3` 或其他 already-solvable regime 做最小 sanity check
3. 若無退化，就把接下來的新 focused learner 驗證先以 hybrid bridge 為主
4. 把研究主線轉向「找新的 genuinely learner-hard family」，而不是一直在 `m4b` 舊 plateau 附近做小修

## 相關輸出

- `p3_6o8c_ultrashort_kmeans_diag/`
- `p3_6o8d_ultrashort_membership_diag/`
- `p3_6o8e_ultrashort_hybrid_bridge/`
- `p3_6m26_m4b_localized_hard_negative_v1/`
- `p3_6m26b_m4b_localized_hard_negative_membership_order/`
- `p3_6p1_m4b_hybrid_bridge/`
- `p3_6m18_m2_normalized_selector_multistart/`
- `p3_6m28_m2_localized_hard_negative_membership_order/`
- `p3_6p2_m2_hybrid_bridge/`
