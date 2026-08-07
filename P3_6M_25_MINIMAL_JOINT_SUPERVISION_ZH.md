# P3.6m-25：最小聯合版 supervision on `m4b`

日期：2026-08-07

## 這一步為什麼值得做

到 `P3.6m-24` 為止，我們已經知道：

1. `boundary-aware replay` 單獨有效的範圍目前只在 `m2`
2. `candidate-conditioned weak-group supervision` 單獨推不動 `m4b`
3. `boundary-aware pair construction` 單獨也推不動 `m4b`

所以最合理的下一步，不是再做第四種 isolated tweak，而是把目前三個已經存在的 learner-side hook 組成一個最小聯合版，直接回答：

- 這三種壓力一起上，能不能把 `m4b` 從 `ue15-only` plateau 稍微推開？

## 目標 regime

- bundle：`p3_6m4b_threshold_nudge_bundle/bundle`
- main family：`0|1|15|2|3|4|5 @ gnb_1`
- train end：`43.6`
- holdout：`43.7 ~ 43.9`

已知 teacher 關鍵 weak group：

- `{ue15, ue4}`

已知 learner / static baseline 舊解：

- `ue15-only`

## 這次的最小聯合版設計

這次不改模型架構，也不改 inference path，只把現有三個 hook 正式綁在一起：

1. `boundary-aware replay`
2. `candidate-conditioned weak-group supervision`
3. `boundary-aware pair construction`

### 實作調整

修改檔案：

- `run_p3_6g_temporal_learner.py`

新增：

- `--joint-supervision-mode`

目前先加入：

- `m4b_minimal_joint_v1`

這個 mode 會自動套用：

- `pair_sampling = teacher_boundary`
- `supervision_weight_mode = teacher_candidate_boundary`
- `candidate_top_k = 2`
- `candidate_membership_weight >= 4.0`
- `candidate_secondary_scale >= 4.0`
- `boundary_support_repeat >= 16`
- `boundary_support_positive_only = true`
- 若未指定，`boundary_support_start = 43.4`

### 新增診斷輸出

這次另外補了一個新的 audit：

- `weak_group_prediction_audit.csv`

它會直接記錄：

- teacher hardest group
- teacher candidate signature
- learner weak-score top-k
- secondary weak candidate 的 rank
- teacher candidates 有幾個真的進到 learner 的 top-k

## focused run

輸出目錄：

- `p3_6m25_m4b_minimal_joint_supervision_v1/`

命令核心條件：

- `restart_seeds = 7 9 11`
- `background_train_limit = 150`
- `feature_mode = history_cost_quality`
- `max_groups = 3`

## 結果

### 主比較結果

- `No grouping = 0.547184178084`
- `CQI = 0.579083105194`
- `Resource-cost = 0.579083105194`
- `Multi-feature = 0.579083105194`
- `Offline teacher = 0.579609048805`
- `LE-GRA = 0.579083105194`

也就是：

- `teacher > LE-GRA = CQI = resource-cost = multi-feature > no-group`

最小聯合版仍然沒有把 holdout 推開。

### support-side

support-side 依然是完美的：

- `support_pairwise = 1.0`
- `support_ari = 1.0`
- `support_nmi = 1.0`
- `support_utility_gap = 0.0`

selected restart seed 仍然是：

- `9`

這表示：

- replay 有作用
- joint supervision 沒有把 support 端弄壞
- 但 holdout decision 仍然沒有改變

## 新增 weak-group audit 告訴了什麼

這一步最重要的 insight，不在主比較表，而在新的
`weak_group_prediction_audit.csv`。

在真正關鍵的三個 holdout 點：

- `43.7`
- `43.8`
- `43.9`

teacher candidate 都是：

- `15|4`

但 learner 預測 top-2 是：

- `15|1`

而且：

- `ue4` 的 `predicted_secondary_rank = 7`

也就是說：

- learner 並不是「已經把 `ue4` 拉到前面，但最後 k-means / DP 沒用上」
- 比較準確的是：
- learner 在最關鍵的 holdout boundary 上，根本還沒有把 `ue4` 視為真正的 secondary weak candidate

## 這一步的研究意義

### 1. minimal learner-side local joint tweaks on `m4b` are still insufficient

這次不是 replay-only。

也不是 candidate BCE-only。

也不是 pair-only。

而是三者最小聯合版一起上。

但結果仍然完全不動，所以現在可以更有把握地下這個結論：

- `m4b` 不是再多一點 local learner-side weighting 就會自己打開

### 2. 問題卡在 `ue4` 根本沒有被拉進 weak-candidate frontier

新的 audit 顯示：

- holdout 上 learner 第一名是對的：`ue15`
- 但第二名不是 `ue4`，而是 `ue1`
- `ue4` 甚至掉到第 7 名

所以目前最精確的 bottleneck 是：

- learner 還沒有學到一個足以把 `ue4` 從 non-weak crowd 中局部拉出的 representation / supervision structure

### 3. 下一步不該再做 replay-only、candidate-BCE-only、pair-only 的微調

這一步已經把 stop-loss 邊界畫得更清楚：

- replay-only：不夠
- candidate BCE weight tuning：不夠
- pair-priority 小修：不夠
- 三者最小聯合版：還是不夠

## 建議下一步

如果接著做，下一步不應再做更多同型的小 sweep。

最合理的方向應該轉成：

1. stronger localized hard negatives  
   直接把：
   - 正確 `{ue15, ue4}`
   - 錯誤 `ue15-only`
   做成更顯式的對比壓力

2. structure-level redesign  
   不再只是改 weighting，而是改 supervision / representation 結構，
   讓 learner 真正需要把 secondary weak candidate 拉出來

## 一句話總結

`P3.6m-25` 證明了：

- 即使把 `boundary replay + candidate supervision + boundary pair construction`
  做成最小聯合版，
- `m4b` 仍然完全卡住；
- 而新的 weak-group audit 顯示，核心原因是 learner 在 holdout 上仍然把
  `ue4` 排在 very low rank，沒有真的學到 teacher 的 dual-weak frontier。
