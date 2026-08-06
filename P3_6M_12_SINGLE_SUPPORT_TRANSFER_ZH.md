# P3.6m-12 single-support transfer check

## 背景

`P3.6m-11` 已經證明：

- 在原始困難設定下
  - `background = 150`
  - `focus_train_repeat = 2`
- 只要加入短暫的 support warmup（`1~3 epochs`）
- LE-GRA 就能對齊 `43.9s` holdout teacher

下一個自然問題是：

**這個 short-warmup protocol 能不能在 support 再變得更少時，仍然轉移到後面的 slice？**

## 測試設定

固定：

- bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
- family: `0|1|15|2|3|4|5 @ gnb_1`
- `background_train_limit = 150`
- `focus_train_repeat = 2`

但把 support 再縮薄：

- train support 只用 `43.7s`
- test holdout 改成 `43.8s ~ 43.9s`

頛詨：

- `p3_6m13_support437_test438_439_baseline/`
- `p3_6m13_support437_test438_439_warmup1/`
- `p3_6m13_support437_test438_439_warmup2/`

## 結果

三組結果全部都沒有成功對齊 teacher：

- baseline
  - `LE-GRA = 0.579083105194`
- warmup 1
  - `LE-GRA = 0.579083105194`
- warmup 2
  - `LE-GRA = 0.579083105194`

也就是說：

- 單一 `43.7s` support snapshot
- 即使加 short warmup
- 仍不足以把 dual-weak rule 穩定轉移到 `43.8 ~ 43.9`

## 解讀

這一步很重要，因為它幫我們把 `P3.6m-11` 的成功條件界定得更清楚。

目前看起來：

- short warmup 確實有效
- 但它不是憑空創造規則
- 它更像是幫 learner 更有效地吸收「已經足夠但稀薄」的 support evidence

換句話說，成功條件大概是：

1. support 需要至少涵蓋不只一個 dual-weak snapshot
2. 然後 short warmup 再把這些 support 的訓練時序排對

而如果 support 只剩單一 snapshot，則目前 learner 仍然不夠穩。

## 到目前為止的最合理結論

把 `P3.6m-8 ~ P3.6m-12` 串起來後，現在可以把 learner bottleneck 描述為：

- not architecture impossibility
- not immediate need for a new dataset
- but a combination of:
  - exact support density
  - support diversity
  - background dilution
  - and curriculum timing

## 建議下一步

最合理的下一步不再是問「warmup 有沒有用」，而是：

**最小成功 support set 到底長什麼樣子？**

例如：

1. 用兩個 support snapshots，但換不同組合
   - `43.7 + 43.8 -> 43.9`
   - `43.7 + 43.9 -> 43.8`
   - `43.8 + 43.9 -> 43.7`

2. 驗證 learner 需要的是：
   - snapshot 數量
   - temporal coverage
   - 還是 specific bridge + dual-weak pairing
