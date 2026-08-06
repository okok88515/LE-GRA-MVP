# P3.6l Dual-Candidate Search 第一輪結果

日期：2026-08-06

## 為什麼進入 P3.6l

在 `P3.6k-4` 與 `P3.6k-5` 之後，問題已經很清楚：

- 現有資料中真正需要 split 的 scenarios 比例太低，約只有 `1%~2%`
- `3|4|5|6 @ gnb_2` 雖然能做出穩定 split，但只支撐「單一明顯弱 user」
- 一旦加入第二個 plausible weak candidate，teacher split 很容易直接 collapse

所以 `P3.6l` 的新方向不是再微調同一條 family，而是：

- 直接搜尋更適合做「雙候選弱 user 競爭」的 family source
- 再基於那個 source 建 targeted generator prototype

## 新增：dual-candidate family miner

新 script：

- `rank_dual_candidate_families.py`

用途：

- 從 near-miss family 中，自動找出最像「兩個弱候選人同時存在」的 family
- 同時要求 family 至少保有基本的 `CQI / resource-cost` 訊號，不只是候選人彼此很像

輸出：

- `p3_6l_dual_candidate_ranking/`
- `p3_6l_dual_candidate_ranking_v2/`

正式採用的是 `v2` ranking。

## Ranking 結果

`p3_6l_dual_candidate_ranking_v2/top10_dual_candidate_family_ranking.csv`

新 top family 變成：

- `1|2|4|5 @ gnb_2`

前幾名重點：

1. `1|2|4|5 @ gnb_2`
2. `0|1|15|2|3|4|5 @ gnb_1`
3. `3|4|5|6 @ gnb_2`

這個結果很重要，因為它表示：

- 當 ranking 真的把「雙候選接近」納入條件時
- `3|4|5|6` 不再是最優先 source
- `1|2|4|5` 更像一個天然含有兩個弱候選人的 family

## Focused audit：`1|2|4|5 @ gnb_2`

輸出：

- `p3_6l2_family_focus/`

摘要：

- `scenario_count = 10`
- `time_window = 23.0s ~ 23.9s`
- `max_teacher_gain_vs_single = 0.0`
- `max_cqi_range = 4.0`
- `max_resource_cost_range = 0.5`
- `max_previous_quality_range = 1.0`

per-user summary：

- `ue 2`
  - `cqi = 12~14`
  - `cost = 3.166667~3.500000`
- `ue 4`
  - `cqi = 11~14`
  - `cost = 3.166667~3.666667`

這比 `3|4|5|6` 更像我們要找的結構，因為：

- `ue 2` 和 `ue 4` 都是 plausible weak candidates
- 而不是只有單一個非常明顯的弱 user

## 新 generator prototype：P3.6l-3

新 builder：

- `build_p3_6l3_dual_candidate_bundle.py`

輸出：

- `p3_6l3_dual_candidate_bundle/`
- `p3_6l3_teacher_audit/`
- `p3_6l3_focus_mining/`

### 設計

Target：

- family: `1|2|4|5 @ gnb_2`
- window: `23.0s ~ 23.9s`

目標是做出：

- `ue 4` = primary weak user
- `ue 2` = competing decoy weak user

具體修改：

- RB-rate transforms
  - `ue 4`: 強 penalty
  - `ue 2`: 較 mild penalty
- previous quality
  - `ue 4 -> 0`
  - `ue 2 -> 1`
  - `ue 1 / ue 5 -> 2`
- history pattern
  - `ue 4`: recent decline
  - `ue 2`: mild recovery

也就是說，這是目前第一個真正依照「雙候選競爭」理念設計的 targeted generator prototype。

## P3.6l-3 結果

Teacher audit 結果很乾脆：

- `1|2|4|5 @ gnb_2` 在 `23.0s ~ 23.9s` 仍然全部維持 single-group
- 沒有新的 positive segment
- `teacher_gain_vs_single = 0.0`

而且在後半段，family 的 aggregate utility 還下降到：

- `0.5721841780840183`

但 teacher 依然不 split。

## 這代表什麼

這是個很有價值的負結果。

它表示：

1. `1|2|4|5` 的確比 `3|4|5|6` 更像雙候選 family source。
2. 但目前這版 generator prototype 還不夠好。
3. 單純把兩個候選人都變弱，並不會自然產生 teacher split。
4. teacher 還是偏向 single-group，而不是在兩個弱候選人之間做更細的分群。

也就是說，目前我們已經把問題再往前推了一步：

- 不只是要找到雙候選 family
- 還要讓其中一個候選人在 split economics 上「夠值得被隔離」
- 另一個候選人則只做到足以干擾 static clustering，但還不該摧毀 teacher split incentive

## 目前最實際的下一步

`P3.6l-3` 後，最值得做的不是回去重跑大 matrix，而是進 `P3.6l-4`：

- 繼續用 `1|2|4|5 @ gnb_2`
- 但不要同時把兩個 candidate 都壓得那麼重
- 改成：
  - `ue 4` 保持明顯 primary weak
  - `ue 2` 只做更輕的 decoy
  - 同時把 `ue 2` 的 temporal history 做得更像假弱點，而不是直接加太多 cost penalty

一句話總結：

`P3.6l` 第一輪證明了新的 family-search 方向是對的，但第一版 dual-candidate generator 還太粗，下一步要改成「弱 decoy、強 primary」而不是「兩個都一起壓」。 
