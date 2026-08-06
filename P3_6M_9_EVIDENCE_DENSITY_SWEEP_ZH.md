# P3.6m-9 evidence-density sweep

## 目標

`P3.6m-8` 已經證明：

- 原 focused learner protocol 的 train 端沒有 exact dual-weak `{ue15, ue4}` teacher slices
- 當 exact dual-weak evidence 被 replay 到夠高密度時，LE-GRA 可以學會 teacher split

`P3.6m-9` 的問題因此變成：

**LE-GRA 需要多少 exact dual-weak support density，才會從「只 isolate ue15」跨到「完整學會 {ue15, ue4}」？**

## 評估設定

固定 regime：

- bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
- family: `0|1|15|2|3|4|5 @ gnb_1`
- support window: `43.7s ~ 43.8s`
- holdout test: `43.9s`

固定 learner recipe：

- feature: `history_cost_quality`
- pair sampling: `teacher_boundary`
- supervision weight: `teacher_hard_group`
- scenario weighting: `positive_multigroup_focus`
- prototype weight: `0.5`
- membership weight: `1.0`
- grouping mode: `membership_order`
- seed: `9`

只掃一個變數：

- `focus_train_repeat ∈ {1, 2, 4, 8, 16, 40, 80}`

background train 固定：

- `background_train_repeat = 1`
- effective background train scenarios = `150`

頛詨：

- `p3_6m9_evidence_density_sweep/`
- summary: `p3_6m9_evidence_density_sweep/sweep_summary.csv`

## 結果摘要

| focus repeat | effective focus train | LE-GRA utility | teacher gap | pairwise | ARI | NMI |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2 | 0.579083 | 0.000526 | 0.714 | 0.417 | 0.428 |
| 2 | 4 | 0.579083 | 0.000526 | 0.714 | 0.417 | 0.428 |
| 4 | 8 | 0.579609 | 0.000000 | 1.000 | 1.000 | 1.000 |
| 8 | 16 | 0.579609 | 0.000000 | 1.000 | 1.000 | 1.000 |
| 16 | 32 | 0.579609 | 0.000000 | 1.000 | 1.000 | 1.000 |
| 40 | 80 | 0.579609 | 0.000000 | 1.000 | 1.000 | 1.000 |
| 80 | 160 | 0.579609 | 0.000000 | 1.000 | 1.000 | 1.000 |

## 最重要的發現

轉折點非常乾淨：

- `repeat = 1, 2`
  - LE-GRA 仍與 multi-feature 打平
  - 尚未學會完整 dual-weak split

- `repeat >= 4`
  - LE-GRA 直接完整對齊 teacher
  - utility、pairwise、ARI、NMI 全部到位

也就是說，在這個 regime 裡：

**臨界點大約出現在 effective focus support 從 `4` 提升到 `8` 個 exact dual-weak slices 之間。**

## 解讀

這個結果很重要，因為它把 bottleneck 描述得更精準了。

不是：

- learner 完全學不會 secondary weak candidate
- 或一定要先重生更大的資料集

而是：

**目前 learner 對 `{ue15, ue4}` 規則是可學的，但對 support density 很敏感；在 evidence 太薄時，它會退回只 isolate `ue15` 的解。**

## 研究意義

`P3.6m-9` 比 `P3.6m-8` 又往前推了一步：

1. `P3.6m-8` 告訴我們 evidence density matters
2. `P3.6m-9` 告訴我們 density threshold 並不高，而且相當明確

這代表下一步最值得做的，仍然是 curriculum / support design，而不是盲目擴大實驗。

## 建議下一步

最合理的 `P3.6m-10` 方向：

1. support-efficient curriculum
   - 不是單純 replay
   - 而是測試更聰明的 sample weighting / mini-batch schedule
   - 看能不能在 `repeat <= 2` 的成本下，逼近 `repeat = 4` 的效果

2. leave-one-support-out / cross-segment holdout
   - 驗證這個 threshold 是否只對 `43.9` 單點成立
   - 或能否轉移到相鄰 family / 相鄰 slice

3. 再決定是否需要重生資料
   - 如果 support-efficient curriculum 做不到
   - 再考慮擴更多 exact dual-weak families 或重生 bundle
