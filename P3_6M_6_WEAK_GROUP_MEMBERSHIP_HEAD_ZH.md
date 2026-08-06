# P3.6m-6 weak-group membership head (prototype-style MVP)

## 目的

`P3.6m-5` 連做三版後，已經把問題收斂得很清楚：

- `v1`：單純 hardest-group pair weighting 不夠
- `v2`：就算補 boundary coverage 和 positive-gain scenario weighting，partition 還是不動
- `v3`：就算加入 weak-group identity prototype supervision，partition 還是不動

因此 `P3.6m-6` 的目的不是再做小 sampling tweak，
而是正式把方向往「weak-group identity learner」推進。

這一版先做一個最小可執行 MVP：

- 不更換整個模型骨架
- 但把 hardest-group membership supervision 明確納入 learner
- 觀察它能不能讓 `LE-GRA` 在 `43.7s ~ 43.9s` 主 regime 上超過 `multi-feature`

## 實作內容

`P3.6m-6` 以 `P3.6m-5 v3` 的 prototype-style weakest-group identity supervision
作為第一版 weak-group membership head MVP。

保留：

- `teacher_boundary` pair sampling
- `positive_multigroup_focus` scenario weighting
- `teacher_hard_group` pair weighting

另外加入：

- `hardest_group_membership(...)`
- prototype-style group-identity loss

其語意已經不再只是 pairwise same/different，
而是把 teacher hardest group 當成一個顯式 supervision target。

## 使用的主評估 regime

- bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
- focus family: `0|1|15|2|3|4|5 @ gnb_1`
- main dual-weak test window: `43.7s ~ 43.9s`
- output: `p3_6m5_group_identity_v3/`

雖然資料夾沿用 `v3` 命名，
但研究上現在把這版正式視為 `P3.6m-6` 的第一個可執行 MVP evidence。

## 結果

### Main comparison

結果仍然是：

- `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`

主要數值：

- `Offline teacher = 0.579609048805`
- `LE-GRA MVP = 0.579083105194`
- `Multi-feature = 0.579083105194`
- `No grouping = 0.547184178084`

### Teacher-imitation diagnostics

三個 test snapshots 仍完全相同：

- `pairwise_accuracy = 0.714285714286`
- `ARI = 0.416666666667`
- `NMI = 0.428140178120`

也就是說：

- weak-group identity signal 已經被納入 learner
- 但最終 partition 仍然沒有從 `ue15-only` 變成 `{ue15, ue4}`

## Train-side evidence

這版 weakest-group identity supervision 並不是沒有生效：

- `train_prototype_positive_terms = 3.6069`
- `train_prototype_negative_terms = 0.0488`
- `prototype_weight = 0.5`

同時也保留了 `v2` 的 coverage 改善：

- `train_negative_pairs = 0.1722`
- `train_priority_negative_pairs = 0.1722`
- `train_schedule_examples = 697.0`
- `train_boosted_scenarios = 7.0`

所以這版的關鍵結論不是「沒教到」，
而是：

- **教到了，但 current embedding + k-means form 仍然接不住**

## 最重要結論

`P3.6m-6` 可以視為一個很重要的負結果：

- 就算 weakest-group membership / identity signal 已經進入 supervision
- 現有 `embedding + k-means` 流程仍無法把它穩定轉成正確的 dual-weak split identity

因此目前最精準的 bottleneck 是：

- 問題不在 feature 不夠
- 問題不在 pair coverage 不夠
- 問題也不只是在 supervision 太弱
- 問題在 learner output form 本身

## 建議下一步

最合理的下一步應該是 `P3.6m-7`，直接改 learner output form，而不是再磨這條 k-means head。

最值得做的方向：

1. direct weak-group membership head
   - 直接輸出每個 UE 屬於 hardest weak group 的分數

2. split-structure prediction head
   - 直接預測誰應該和 primary weak user 一起進弱組

3. soft teacher partition supervision
   - 把 near-best partition / uncertain weak membership 一起納入

一句話總結：

`P3.6m-6` 已經證明，單靠在現有 embedding 上加 weakest-group identity supervision，還不足以讓 LE-GRA 學會 `{ue15, ue4}`；下一步應該直接改 learner 的輸出形式。
