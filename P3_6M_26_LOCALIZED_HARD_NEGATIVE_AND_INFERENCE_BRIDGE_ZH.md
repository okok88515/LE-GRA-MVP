# P3.6m-26：localized hard negatives + inference bridge

日期：2026-08-07

## 這一步在做什麼

`P3.6m-25` 已經把一件事釘得很清楚：

- 最小聯合版 supervision 還是推不動 `m4b`
- 而且 learner 在 holdout 上仍然把 `ue4` 排得很後面

所以這一步我做了兩個連續動作：

1. 加入更強的 localized hard-negative supervision
2. 檢查真正的 bottleneck 是否其實在 inference bridge，而不是 learner 完全學不到

## 第一部分：localized hard negatives

### 核心想法

前面幾輪 supervision 的問題是：

- 有教誰是 weak candidate
- 但沒有明確教「`ue4` 必須贏過哪些容易被誤認的 confuser」

所以這次不是只加正樣本權重，而是直接在 weak head 上加局部排序壓力：

- teacher candidates 必須排在局部 confusers 前面

這裡最重要的對比就是：

- 正確：`{ue15, ue4}`
- 舊錯解前緣：`ue15 + 某個 confuser`

### 程式實作

修改檔案：

- `le_gra_mvp.py`
- `run_p3_6_coupled_learner.py`
- `run_p3_6g_temporal_learner.py`

新增：

- `candidate_frontier_contrast_targets(...)`

它會建立：

- frontier positives：teacher hardest group 的 top resource-cost candidates
- frontier negatives：最接近的局部 confusers
  - 先取 hardest group 裡的 non-candidates
  - 再補全域高 resource-cost non-candidates

然後在 `MLPEncoder.train_step(...)` 上新增：

- `frontier_contrast_weight`
- `frontier_margin`

loss 形式是局部 ranking-style margin loss：

- 正 candidate 的 weak logit 必須高於 confuser

### focused mode

在 `run_p3_6g_temporal_learner.py` 新增：

- `m4b_localized_hard_negative_v1`

它會自動套用：

- `pair_sampling = teacher_boundary`
- `supervision_weight_mode = teacher_candidate_boundary`
- `candidate_membership_weight >= 4.0`
- `candidate_secondary_scale >= 4.0`
- `frontier_contrast_weight >= 6.0`
- `frontier_negative_top_k >= 2`
- `frontier_margin >= 0.25`
- `boundary_support_repeat >= 16`
- `boundary_support_positive_only = true`
- default `boundary_support_start = 43.4`

## 第二部分：先用原本 inference path 測一次

輸出：

- `p3_6m26_m4b_localized_hard_negative_v1/`

設定：

- `grouping_mode = kmeans_embedding`

### 結果

主 utility 還是沒動：

- `teacher = 0.579609048805`
- `LE-GRA = 0.579083105194`

但這次和前面不一樣，新的 weak-group audit 顯示：

- 在 `43.7 / 43.8 / 43.9`
- teacher candidate = `15|4`
- learner predicted top-2 也變成 `15|4`
- `ue4` 的 rank 從先前的 `7` 直接升到 `2`

這是非常重要的變化。

## 第三部分：inference bridge 檢查

上面的結果帶出一個很關鍵的懷疑：

- learner 其實已經把 weak boundary 學對了
- 但最後 evaluation 仍然走 `kmeans_embedding`
- 所以 weak head 的正確訊號沒有被真正轉進最終 grouping

因此我立刻做了一個 focused bridge check：

輸出：

- `p3_6m26b_m4b_localized_hard_negative_membership_order/`

唯一關鍵改動：

- `grouping_mode = membership_order`

也就是直接讓 inference 使用 weak-group scores 做 ordered boundary search，
而不是再回到 embedding k-means。

## 關鍵結果

這一步是今天最重要的突破。

在 `membership_order` 下：

- `Offline teacher = 0.579609048805`
- `LE-GRA = 0.579609048805`

也就是：

- `LE-GRA` 直接追平 teacher

## 這代表什麼

### 1. learner 並不是永遠學不到 dual-weak

前面的 impression 比較像：

- 不管怎麼教，learner 都抓不到 `{ue15, ue4}`

但 `P3.6m-26` 證明這個說法已經不成立。

比較準確的是：

- 在 localized hard negatives 之後，weak head 已經能學到正確的 dual-weak frontier

### 2. 先前真正的 bottleneck 很大一部分是 inference mismatch

也就是：

- 訓練時新增的 weak-group supervision
- 確實把 weak head 推對了

但 evaluation / deployment path 仍然是：

- embedding -> k-means

這條路沒有直接使用 weak head 的排序訊號。

所以前面很多「看起來沒進展」的 run，現在回頭看，很可能不是 learner 毫無學習，而是：

- 學到的訊號被放在沒有被 inference 使用的 head 裡

### 3. 研究主線要開始轉向「representation-supervision」改成「inference-bridge」

現在最值得問的問題不再是：

- 要不要再加一個小 supervision tweak？

而是：

- 如何把已經學到的 weak-boundary 訊號，穩定轉進最終 grouping path？

## 建議下一步

接下來最值得做的，不是回頭再做更多 local loss 微調，而是沿著這個突破往下推：

1. 把 `membership_order` 視為正式 bridge candidate  
   系統性比較：
   - `kmeans_embedding`
   - `membership_order`

2. 檢查它是不是只在 `m4b` 有效，或也能 transfer 到其他 focused regimes

3. 若要保留 embedding path，考慮做 hybrid bridge  
   例如：
   - weak-head-guided embedding clustering
   - weak-head-informed candidate boundary initialization

## 一句話總結

`P3.6m-26` 的核心突破是：

- localized hard negatives 已經把 holdout 上的 weak ranking 修正到
  `15|4`
- 真正卡住 LE-GRA 的，已不只是 learner-side supervision，
  而是 `weak head` 與最終 `grouping path` 之間的 inference mismatch；
- 一旦改用 `membership_order`，`LE-GRA` 就能在 `m4b` 上追平 teacher。
