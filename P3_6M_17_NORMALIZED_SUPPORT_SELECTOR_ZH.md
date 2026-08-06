# P3.6m-17 Normalized Support Selector

日期：2026-08-06

## 這一步要回答的問題

前一輪 `P3.6m-16` 的結論是：

- focused multi-start 有效
- 但 support-side imitation signal 看起來不夠強
- 最後常常要靠 training loss tie-break 才能選出好 seed

這讓我們懷疑兩種可能：

1. 真的沒有夠好的 local validation signal
2. 其實 signal 有，只是我們上一版 selector 的評分方式有偏差

`P3.6m-17` 的目的就是把這兩件事拆開。

## 核心發現

答案是第 2 種。

上一版 selector 最大的問題不是「訊號太弱」，而是：

- `_score_restart_candidate(...)` 當時拿來評分的 support slices，
  不是 candidate 真正訓練後所在的 normalized feature space

也就是說：

- model 是在 training-time normalized scenario 上學習
- 但 restart selector 卻在 pre-normalization 的 support scenario 上評分

這會把 seed 間本來存在的差異壓扁。

## 實作修改

修改檔案：

- `run_p3_6g_temporal_learner.py`

修正方式：

- 不再用原始 `focus_train` 當 selector 評分資料
- 改用 actual training copy 裡、已經經過 feature-mode + normalization 的
  support slices 來做 candidate scoring

另外也順手把更多 candidate-level 指標記進 `restart_candidates.csv`：

- `support_contrastive_loss`
- `support_weak_bce`
- `support_weak_margin_min`
- `support_weak_margin_mean`
- `support_proto_sep_margin`

## 實驗設定

沿用同一個 focused regime：

- family/regime：`0|1|15|2|3|4|5 @ gnb_1`
- bundle：`p3_6m4b_threshold_nudge_bundle/bundle`
- `background_train_limit = 150`
- `focus_train_repeat = 2`
- `focus_only_warmup_epochs = 1`
- `restart_seeds = [7, 9, 11]`
- 主呼叫 seed 仍設成 `9`

三個 transfer case：

1. `43.7 + 43.8 -> 43.9`
2. `43.8 + 43.9 -> 43.7`
3. `43.7 + 43.9 -> 43.8`

輸出目錄：

- `p3_6m17_selector_fix_support437_438_test439/`
- `p3_6m17_selector_fix_support438_439_test437/`
- `p3_6m17_selector_fix_support437_439_test438/`

## 結果

### 1. 修正後，support selector 自己就能分出好壞 seed

三個 case 都出現同樣形狀：

- seed `7`
  - `support_pairwise = 1.0`
  - `support_ari = 1.0`
  - `support_nmi = 1.0`
  - `support_utility_gap = 0.0`
- seed `9`
  - `support_pairwise = 0.714285714286`
  - `support_ari = 0.416666666667`
  - `support_nmi = 0.428140178120`
  - `support_utility_gap = -0.000525943612`
- seed `11`
  - `support_pairwise = 1.0`
  - `support_ari = 1.0`
  - `support_nmi = 1.0`
  - `support_utility_gap = 0.0`

這跟真實 holdout transfer 成敗完全對齊：

- seed `7` / `11` 會成功
- seed `9` 會失敗

### 2. 三個 case 都乾淨選到 seed 11

三個目錄的 `split_summary.json` 都顯示：

- `selected_restart_seed = 11`

而且這次不是因為前面的 support 指標都平手才被迫進到 fallback，
而是 support-side 的主指標本身就已經足夠把 seed `9` 排除。

### 3. 額外指標也支持同一個方向

三個 case 中，seed `11` 也都表現出：

- 更低的 `support_contrastive_loss`
- 更低的 `support_weak_bce`
- 更大的 `support_proto_sep_margin`

例如 `43.7 + 43.8 -> 43.9`：

- seed `7`
  - contrastive = `0.062743841935`
  - weak BCE = `0.711460257423`
  - proto sep = `0.492613870212`
- seed `9`
  - contrastive = `0.110295138870`
  - weak BCE = `0.696632746048`
  - proto sep = `0.229364091293`
- seed `11`
  - contrastive = `0.049450787715`
  - weak BCE = `0.642466962233`
  - proto sep = `0.520808536643`

其中最穩定、最直接可用的 selector 仍然是：

- normalized support 上的 teacher-imitation metrics

## 最重要的研究結論

這一步真正重要的地方是：

- 我們現在已經證明「好的 local validation signal 是存在的」
- 前一版 selector 看起來弱，主要不是因為訊號本身不行
- 而是因為 selector 在錯的 feature space 上做評分

換句話說：

- 現在的 learner-focused pipeline 已經不只是「能靠 multi-start 碰到成功 seed」
- 而是「能用合理的 normalized support validation，主動把失敗 seed 排掉」

## 這對後續方向的影響

這會直接改變下一步判斷。

我現在不會優先建議：

- 再回去做新的 learner head 微調
- 或立刻擴大整體矩陣

更合理的是：

1. 把 normalized-support restart scoring 視為目前 focused learner 的正式 protocol
2. 用這個 protocol 去測試：
   - 更遠一點的 nearby slice
   - 或 nearby family / nearby regime

## 目前的定位

這一步可以視為一個很不錯的研究收斂點。

因為到這裡我們已經完成三件事：

1. 找到最小成功 support set
2. 確認成功不是單一 seed 幻象
3. 找到能在 local scope 上辨識好壞 seed 的正確 validation signal

所以如果下一步還要繼續，我會建議不要再做新的 selector 猜測，
而是先拿這個修正後的 focused protocol 去做更有外部意義的 transfer 測試。
