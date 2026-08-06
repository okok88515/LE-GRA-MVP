# P3.6j Targeted Scenario Redesign v2

Last updated: 2026-08-06

## 目標

P3.6g、`seg_02`、`seg_01` 已經回答了一個重要問題：

> LE-GRA 在 coupled trace-like regime 上不是學不起來；
> 只要 train/test 對齊到真正存在的 positive-gain split regime，
> 它可以完整重現 offline teacher。

但這還不是最終想要的研究結論。下一步真正要追的是：

1. 拉大 `teacher` 與其他方法的差距
2. 拉大 `LE-GRA` 與 `multi-feature` 的差距
3. 讓 `no-group` 明顯更差，證明分群真的有價值

也就是說，P3.6j 的目標不是再做一次「可重現 teacher」，
而是設計出一個更能放大方法差異的 coupled regime。

## 為什麼現在差距還不夠大

目前最強的 focused slices 有兩個特徵：

- `teacher` 明確優於 `no-group`
- `LE-GRA` 與 `multi-feature` 都能完美追上 `teacher`

這代表目前的 split 規則雖然是真實存在的，但還不夠複雜。
從研究角度看，現在的 regime 比較像：

- 有分群需求
- 但手工特徵已經足以描述最佳 split

如果我們想讓 `LE-GRA > multi-feature`，就必須讓最佳決策更依賴：

- 時間脈絡
- previous-quality 差異
- 非單調的 CQI / resource-cost tradeoff
- cross-traffic 導致的短時 decision flip

## 設計原則

P3.6j 不走 P3.6i 的激進路線，也不只是重複 P3.6i-2。
這一輪的設計原則是：

### 1. 不破壞 informative overlap

要保留目前已知有效的互動骨架：

- northbound 主族群
- cross-traffic `15`、`31`
- `gnb_1` / `gnb_2` overlap 區域

也就是說，不能再用大幅拉開 spacing 的方式硬做壓力。

### 2. 讓 decision 更依賴 temporal context

我們要故意做出這種情況：

- 同一個 user 在連續幾個 snapshots 內，是否該被 isolate 會改變
- 單看某一個 snapshot 的手工特徵還不夠
- 但看歷史趨勢可以比較穩地抓到 teacher 規則

這才有機會讓 LE-GRA 比 Multi-feature 更有價值。

### 3. 讓 previous_quality 真的成為有效訊號

P2.6 已經告訴我們 `history_cost_quality` 很重要。
所以 P3.6j 要讓 `previous_quality` 不是裝飾，而是直接影響 split 決策。

## P3.6j 要刻意創造的三種機制

### 機制 A：Previous-quality divergence

做法：

- 在主 family 中，讓部分 UE 維持較高 previous quality
- 另一部分 UE 維持較低 previous quality
- 這個差異在進入 overlap 區時不要立刻消失

目標：

- 拉大 `teacher` 對 switching / quality continuity 的敏感度
- 讓 `no-group` 更容易吃到品質一致性與資源分配的雙重損失
- 讓只看靜態 snapshot 的方法比較難判斷該 isolate 誰

### 機制 B：CQI 與 resource-cost 排序不完全一致

做法：

- 保留寬頻 CQI 接近的 UE
- 但讓 per-band TBS profile、effective RB cost、或 serving-gNB 幾何位置略有錯位
- 目標不是完全隨機，而是「wideband 看起來差不多，但實際資源代價不同」

目標：

- 放大 `teacher` 相對於 `CQI` 與 `no-group` 的優勢
- 讓 `multi-feature` 不能只靠一組 snapshot 統計就穩定決策
- 增加 `ambiguous pair` 的研究價值

### 機制 C：Cross-traffic induced temporal flip

做法：

- 讓 `15` 或 `31` 在關鍵時間窗進入／離開壓力區
- 讓某個 UE 在 `t` 時刻適合併在主群，`t+1` 時刻反而更適合被 isolate
- 這個切換要短，但不能只剩一個 snapshot

目標：

- 讓 `teacher` 相對於靜態方法有更高增益
- 讓 LE-GRA 有機會靠 temporal history 跟上
- 讓 `seg_01` / `seg_02` 進一步演化成「會翻轉」而不是「固定 isolate 同一人」

## 建議的實作順序

P3.6j 不建議一次同時改太多。最有效率的順序是三階段：

### P3.6j-1：Quality-divergence variant

先只動 `previous_quality` 控制，不大改 mobility。

要做的事：

- 在現有 `p3_6i2` 有效 family 上，為 `0..5` 或 `0..6` 設計更分離的 quality state
- 保留 `rb_budget_ratio = 0.28`
- 重跑 teacher audit 與 focus mining

成功標準：

- `positive_gain_count` 高於 `9`
- `max_teacher_gain_vs_single` 高於 `0.05716`
- 新 family 不是只有原本那兩段重現，而是出現更長或更多正增益區間

### P3.6j-2：Cost-order mismatch variant

如果 j-1 成功，再引入較小幅度的幾何 / 無線條件錯位。

要做的事：

- 微調特定 UE 的速度或進入 overlap 區時間
- 保持 wideband CQI 接近
- 但增加 per-band TBS dispersion 與 mean resource-cost range

成功標準：

- `teacher` 對 `CQI k-means` 與 `no-group` 的 gap 擴大
- `multi-feature` 不再穩定完美 imitation

### P3.6j-3：Temporal-flip variant

最後才做最難的「短時間最佳 split 對象翻轉」。

要做的事：

- 讓 `15` / `31` 或某個主群 UE 在壓力區內造成 family composition 微調
- 觀察是否出現：
  - `t1`: isolate A
  - `t2`: isolate B

成功標準：

- teacher split identity 在相鄰 snapshots 內改變
- Multi-feature 開始掉 imitation
- LE-GRA 若仍能維持高 imitation，就真正有研究價值

## 每一階段都要看的指標

除了 utility 之外，P3.6j 每輪都要固定檢查：

1. `positive_gain_count`
2. `positive_segment_count`
3. `candidate_temporal_slice_count`
4. `max_teacher_gain_vs_single`
5. `cqi_range`
6. `resource_cost_range`
7. `ambiguous-pair ratio`
8. `teacher group identity` 是否在相鄰時間翻轉
9. `LE-GRA` 與 `Multi-feature` 的 pairwise / ARI / NMI
10. `teacher - LE-GRA`、`teacher - multi-feature`、`teacher - no-group` 的 utility gap

## 這一步最重要的判準

P3.6j 的成功，不是只看有沒有再找到 positive split family。

真正的成功標準是：

> teacher 仍然明顯優於 no-group，
> Multi-feature 不再總是完美追上 teacher，
> 而 LE-GRA 至少在其中一部分 temporal slices 上比 Multi-feature 更穩。

如果只做到 `teacher = LE-GRA = multi-feature > no-group`，
那仍然只是證明「分群有用」，還沒有把 LE-GRA 的獨特價值拉出來。

## 目前最推薦先做的版本

如果只能先做一個版本，最推薦從 **P3.6j-1 quality-divergence variant** 開始。

理由：

1. 風險最低
   - 不會像 P3.6i 那樣破壞整體 traffic structure
2. 與既有結論一致
   - P2.6 已經告訴我們 previous quality 是有效訊號
3. 最容易放大 teacher 與 no-group 的差距
4. 也最有機會讓決策更依賴 temporal context，而不是只靠 snapshot 特徵

## 建議的下一個實際動作

下一個實作任務建議定義為：

### P3.6j-1：quality-divergence redesign

要做的事：

1. 以 `p3_6i2` 為底，不動主體 route 拓樸
2. 重新設計 deterministic quality-state controller
3. 刻意讓主 family 在進入 overlap 區前就帶著較大的 previous-quality 差異
4. 重跑：
   - coupled simulation
   - bundle
   - teacher audit
   - focus mining
5. 比較：
   - 是否出現比 `seg_01` / `seg_02` 更長或更高增益的 slices
   - 是否開始讓 `multi-feature` 與 `teacher` 出現差距

## 目前可以放進報告的敘述

> Based on the P3.6g, seg_02, and seg_01 results, the next research step is not
> immediate learner expansion. The more valuable direction is scenario redesign
> that preserves informative coupled interactions while increasing decision
> dependence on previous-quality divergence, resource-cost ambiguity, and
> short-horizon temporal flips. This is the most promising path to widen the gap
> between the offline teacher and weaker baselines, and potentially expose a
> regime where LE-GRA outperforms snapshot-based multi-feature clustering.
