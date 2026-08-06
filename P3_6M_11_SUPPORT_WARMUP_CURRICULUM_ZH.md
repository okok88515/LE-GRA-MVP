# P3.6m-11 support warmup curriculum

## 背景

`P3.6m-10` 已經證明：

- `focus_train_repeat = 2` 在原始 `background = 150` 下會失敗
- 但只要降低 background dilution，就會成功

因此下一個自然問題是：

**如果不增加 support、也不減少 background，只改 support 的出場順序，能不能也成功？**

這就是 `P3.6m-11`。

## 方法

在 `train_trace_model(...)` 加入：

- `focus_support_indices`
- `focus_only_warmup_epochs`

做法很簡單：

- 前幾個 epoch 只用 exact support slices 訓練
- 後面的 epoch 再回到完整混訓

這是一種 schedule-aware curriculum，不需要：

- 新資料
- 更多 unique support
- 更大的實驗矩陣

## 固定設定

全部實驗都固定在最困難、也是最有價值的那個原始設定：

- bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
- support window: `43.7s ~ 43.8s`
- holdout test: `43.9s`
- `background_train_limit = 150`
- `focus_train_repeat = 2`
- exact focus support = `4`
- seed = `9`

也就是說：

**這裡唯一改的只有 curriculum。**

頛詨：

- `p3_6m12_repeat2_bg150_warmup1/`
- `p3_6m12_repeat2_bg150_warmup2/`
- `p3_6m12_repeat2_bg150_warmup3/`
- `p3_6m12_repeat2_bg150_warmup4/`
- `p3_6m12_repeat2_bg150_warmup6/`

## 結果

| warmup epochs | LE-GRA utility | teacher gap | 結果 |
|---:|---:|---:|---|
| 1 | 0.579609 | 0.000000 | success |
| 2 | 0.579609 | 0.000000 | success |
| 3 | 0.579609 | 0.000000 | success |
| 4 | 0.579083 | 0.000526 | fail |
| 6 | 0.579083 | 0.000526 | fail |

## 最重要的發現

這是目前整個 P3.6m 脈絡裡非常關鍵的一步：

**只靠短暫的 support warmup（1~3 epochs），就可以讓原本失敗的 `repeat=2, background=150` 設定成功對齊 teacher。**

換句話說：

- 不必把 support replay 到 `repeat=4`
- 不必先砍掉大量 background
- 不必重生資料

只要把 exact dual-weak support 提前、而且集中地看幾個 epoch，LE-GRA 就能學會。

## 另一個同樣重要的現象

`warmup = 4, 6` 反而失敗，表示：

- support warmup 並不是越長越好
- 太長的 support-only 階段，可能讓 learner 對極小 support set 過度偏置
- 後續回到完整背景混訓時，反而無法穩定保留正確 partition

也就是說，目前看到的不是單調效果，而是一個：

**short warmup sweet spot**

大致落在：

- `1 ~ 3 epochs`

## 解讀

`P3.6m-8 ~ P3.6m-11` 串起來後，現在 bottleneck 已經可以描述得很清楚：

1. learner 並不是無法表示 `{ue15, ue4}`
2. exact support 的密度很重要
3. background dilution 很重要
4. 但更核心的是：

**support 出現在訓練過程中的時序，也很重要**

也就是說，這已經不只是 data quantity 問題，而是：

- curriculum / scheduling 問題

## 目前最佳方向

到這一步為止，最值得投資的下一步已經很明確：

1. 把 warmup curriculum formalize 成可重跑 protocol
2. 檢查這個 short-warmup sweet spot 是否能轉移到：
   - 相鄰 holdout
   - 相鄰 family
   - 相鄰 positive segment
3. 之後才決定是否真的要擴資料或重生 bundle

## 目前最強結論

如果只用一句話總結 `P3.6m-11`：

**在這個 dual-weak regime 下，LE-GRA 的失敗不是模型做不到，而是 exact support slices 沒有在正確的時機、以足夠但不過量的方式進入訓練。**
