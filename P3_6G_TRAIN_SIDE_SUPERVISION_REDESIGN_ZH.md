# P3.6g Train-side Supervision Redesign

更新日期：2026-08-06

## 這一步在解什麼問題

P3.6e 與 P3.6f 已經證明兩件事：

1. `rb_budget_ratio = 0.32` 的 coupled trace 裡，offline teacher 的確開始出現真正有正增益的 split decision。
2. 這些正增益 case 幾乎全部集中在同一組 UE：`0|1|2|3`。

但 P3.6f 也暴露出一個更關鍵的問題：

- 如果把 `0|1|2|3` 全部放進 test slice，learner 在 train 期間其實看不到真正的 split-gain supervision。
- 結果就是 test set 雖然終於有 informative split case，但 learner 仍然是「拿沒有學過的 supervision 類型去考試」。

因此 P3.6g 的目標不是再換模型，而是先重設 supervision protocol，確認 learner 到底有沒有能力在 coupled trace 上學到 teacher 的 split 行為。

## 核心想法

這次改成 **focused temporal split**：

- 固定 focus UE 為 `0|1|2|3`
- 不再把這四個 UE 全部丟到 test，而是依時間切開
- `train window <= 15.9s`
- `test window = 16.0s ~ 18.0s`

這樣做的目的，是讓 train 與 test 都來自同一組 UE、同一種 coupled trace 機制，但 test 仍然保留「未來時間窗」的泛化要求。

換句話說，這不是把答案直接洩漏給 learner，而是改成比較合理的問題設定：

- train 先看過一部分真實 split-gain 狀況
- test 再評估它能不能在後續時間窗延續同樣決策

## 正增益 case 的時間分布

從 `p3_6f_teacher_audit/learner_test_split/scenario_teacher_decisions.csv` 可見：

- `14.0s ~ 15.1s` 有一段正增益 split 區間
- `15.2s ~ 16.0s` 中間有短暫 neutral 區
- `16.1s ~ 17.0s` 再出現第二段正增益 split 區間
- `17.6s ~ 17.7s` 還有少量尾端正增益 case

因此用 `15.9s / 16.0s` 作為 temporal boundary，可以得到：

- train 端有一批真正的 positive-gain split supervision
- test 端也保留一批真正的 positive-gain split case

## 實作

新增腳本：

- `run_p3_6g_temporal_learner.py`

它的切法是：

1. 背景 train UE 仍沿用原本的 background train slice
2. `0|1|2|3` 的 focused scenarios 再依 timestamp 切成 train/test
3. train = background train + focused early window
4. test = focused later window

預設設定：

- `bundle_dir = p3_6e3_coupled_bundle/bundle`
- `feature_mode = history_cost_quality`
- `max_groups = 3`
- `rb_budget_ratio = 0.32`
- `seed = 9`

## 結果

輸出目錄：

- `p3_6g_temporal_learner/`

### Split summary

- `background_train_scenarios = 556`
- `focus_train_scenarios = 100`
- `focus_test_scenarios = 21`
- `focus_train_positive_gain_count = 12`
- `focus_test_positive_gain_count = 12`
- `selected_epoch = 11`
- `selection_validation_loss = 0.004503`

這是 P3.6g 最重要的變化：

- P3.6f 的 train 端幾乎沒有真正的 split supervision
- P3.6g 的 train 端終於有 `12` 個正增益 split case

### Main comparison

- `No grouping`: utility `0.6402`
- `CQI k-means`: utility `0.6622`
- `Resource-cost k-means`: utility `0.6622`
- `Multi-feature k-means`: utility `0.6622`
- `Offline teacher`: utility `0.6622`
- `LE-GRA MVP`: utility `0.6622`

也就是說，在這個 temporal focused split 上：

- LE-GRA 已經追平 offline teacher
- LE-GRA 也追平 multi-feature / resource-cost k-means
- 相較於 no grouping，utility 有明顯提升

### Teacher imitation diagnostics

`teacher_imitation_diagnostics.csv` 顯示：

- `Multi-feature k-means`: pairwise / ARI / NMI 全部 `1.0`
- `LE-GRA MVP`: pairwise / ARI / NMI 也全部 `1.0`

代表在這 21 個 focused future-window 測試情境上：

- teacher 要 1 群時，LE-GRA 判成 1 群
- teacher 要 2 群時，LE-GRA 判成 2 群
- partition 結果與 teacher 完全一致

## 研究意義

P3.6g 的價值不在於「數字又多好看一點」，而是在研究判讀上把問題切得更清楚：

### 1. 先前 learner 失敗，不只是模型太弱

P3.6f 已經顯示，原本的 split protocol 有 supervision mismatch：

- train 幾乎沒看到正增益 split
- test 卻要求 learner 判出正增益 split

這種設定下，學不起來不一定代表 embedding 無效，也可能只是 train/test supervision 不對齊。

### 2. 當 train 真的看過 split-gain supervision，LE-GRA 可以學到

P3.6g 把 train-side supervision 補齊之後，LE-GRA 在未來時間窗 test 上可以完全重現 teacher partition。

因此目前更合理的結論是：

- bottleneck 不是「LE-GRA 永遠學不到 coupled split」
- bottleneck 是「train slice 需要真的包含 informative split-gain supervision」

### 3. 這是 protocol insight，不只是單次實驗技巧

如果未來 coupled trace 研究要擴大：

- 不能只看 UE-based split 有沒有隔離乾淨
- 還要檢查 train 端是否真的覆蓋到 teacher 會切群的 regime

否則 learner 可能會被錯誤地評估成「在真實 trace 上沒用」。

## 目前仍然保留的限制

這一輪還不能直接宣稱「LE-GRA 已經全面勝出」，原因有三個：

1. `focus_test_scenarios` 只有 `21` 個，樣本仍小。
2. 這是單一 focused UE 組合 `0|1|2|3` 的 temporal generalization，還不是跨更多 split regime 的普遍結論。
3. 在這個 slice 上，`Multi-feature k-means` 也同樣達到 `1.0` diagnostics，因此目前能證明的是「LE-GRA 可以學到」，還不是「LE-GRA 已經明顯超越 hand-crafted baseline」。

## 現在最合理的結論

P3.6g 成功回答了目前最重要的研究問題：

> 如果 coupled trace 裡真的存在正增益 split case，並且 train 端也看得到這種 supervision，LE-GRA 能不能學到 teacher decision？

答案是：可以，而且在目前這個 focused temporal split 上，LE-GRA 已經與 offline teacher 完全對齊。

## 建議下一步

最自然的下一步不是立刻改 learner 架構，而是先擴大這個結論的可信度：

1. 建立更多 **train/test 都含正增益 split** 的 focused temporal slices。
2. 檢查是否只有 `0|1|2|3` 這組 UE 有效，還是其他高壓局部群組也成立。
3. 若多個 focused slice 都成立，再進一步比較：
   - LE-GRA 是否比 multi-feature 更穩定
   - 哪些特徵真的對 temporal generalization 有幫助
4. 之後才值得進入更大的 coupled learner matrix。

