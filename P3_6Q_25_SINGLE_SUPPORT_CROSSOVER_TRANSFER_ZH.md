# P3.6q-25: 只要把 `28.3s` 納進 support，`28.4 ~ 28.8` 就能整段回到 teacher

## 背景

`P3.6q-24` 已經把新的 dual-boundary crossover regime 定位得很清楚：

- teacher 在 late corridor `28.3s ~ 28.8s` 穩定偏好 `3|5 / 4|6`
- `multi-feature k-means` 在這段全部塌成 single-group
- plain `LE-GRA` 已經能在 `28.4 ~ 28.8` 跟上 teacher
- 但在最早的 crossover onset `28.3` 還會失敗

所以這一輪要回答的問題只有一個：

- `28.3s` 到底是整段 late regime 都不會，還是只差最早那一步？

## 實驗設計

我做了最小 single-support transfer：

- train end = `28.3`
- test = `28.4 ~ 28.8`

也就是：

- 先把最早的 crossover onset `28.3` 納進 train/support
- 再看後面的 `5` 個 snapshots 是否能整段穩定

跑了兩組：

1. plain probe
   - `p3_6q25_support283_test284_288_plain/`
2. anchor + margin probe
   - `p3_6q25_support283_test284_288_anchor_margin/`

## plain probe 結果

Artifact:

- `p3_6q25_support283_test284_288_plain/`

主結果：

- `No grouping = 0.5721841780840183`
- `Multi-feature k-means = 0.5721841780840183`
- `Offline teacher = 0.5790955890522329`
- `LE-GRA MVP = 0.5790955890522329`

也就是：

- plain `LE-GRA` 直接回到 full teacher match

## anchor + margin probe 結果

Artifact:

- `p3_6q25_support283_test284_288_anchor_margin/`

主結果：

- `Offline teacher = 0.5790955890522329`
- `LE-GRA MVP = 0.5790955890522329`

這組當然也成功，
但更重要的是它沒有比 plain support283 版本再多帶來新的增益。

## 這代表什麼

這個結果非常關鍵，因為它把 `q23/q24` 的 bottleneck 收斂得更準：

- 問題不是整個 late crossover corridor 太難
- 問題也不是需要更重的 grouping bridge
- 問題是：
  **LE-GRA 缺少最早的 crossover onset 支撐點**

更直白地說：

- 一旦模型看過 `28.3s`
- 後面的 `28.4 ~ 28.8` 幾乎就自然接起來了

## 新的研究判讀

`q23/q24/q25` 現在可以連成一條很完整的故事：

### `q24`

- plain baseline 完整失敗
- plain LE-GRA 幾乎成功
- 唯一缺口是 `28.3s`

### `q25`

- 只補一個 `28.3s` support
- `28.4 ~ 28.8` 就整段回到 teacher

所以這條 regime 最準確的 diagnosis 是：

- not a full late-corridor failure
- not a generic grouping collapse
- it is an **earliest-onset crossover generalization failure**

## 對下一步的意義

這對接下來的研究很重要，因為它大幅縮小了搜索空間。

現在不需要再問：

- 要不要重做整條 regime？
- 要不要做更重的全域 supervision redesign？

現在該問的是：

- 怎麼讓模型在**沒看過 `28.3s` 的情況下**
  也能把 `ue5 -> ue6` 的 secondary-weak switch 提前一步學會？

## 最值得做的下一步

接下來最合理的方向是做「不直接把 `28.3s` 放進 train」的最小模擬：

1. `28.3`-adjacent boundary replay
   - 例如重播 `27.x` 後段最接近 switch 的 support examples
2. candidate-switch calibration
   - 直接強化 `ue6` 在 late onset 的 secondary role
3. localized pre-onset support
   - 不偷看 `28.3`
   - 只加強 `27.9 ~ 28.2` 這種最接近 onset 的前置區段

## 一句話總結

這次最大的收穫不是「又 match 一個 case」，
而是我們現在已經知道：

- 這條新 benchmark-like regime 真正缺的只是一個 earliest crossover onset 的泛化能力，
- 而不是整段 late regime 都學不起來。
