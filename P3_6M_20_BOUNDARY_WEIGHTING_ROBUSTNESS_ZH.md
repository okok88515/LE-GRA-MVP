# P3.6m-20：boundary-aware support weighting 的第一輪 robustness check

日期：2026-08-06

## 這一步要回答的問題

`P3.6m-19` 已經給了我們一個很強的正面訊號：

- 在 `m2` 上，只靠最小版 boundary replay
- `LE-GRA` 就能從原本卡住的 plateau
- 一路追到 teacher

但那時候還有兩個合理懷疑：

1. 會不會只是剛好 `boundary_support_start = 43.4` 這個值很巧？
2. 會不會只是 `43.8 ~ 43.9` 這個兩格 holdout 剛好碰巧成立？

所以這一步不做大實驗，只做兩個很小、但資訊量很高的 robustness check。

## 固定條件

bundle：

- `p3_6m2_positive_family_decoy_bundle/bundle`

共同設定：

- `train_window_end = 43.7`
- `boundary_support_repeat = 16`
- `boundary_support_positive_only = true`
- `restart_seeds = 7 9 11`
- focus family:
  - `0|1|15|2|3|4|5 @ gnb_1`

在這個設定下，被選進 boundary replay 的 support slice 仍然只有：

- `1` 個

這點很重要，因為代表我們還是在非常小的 supervision 改動下測試。

## A. boundary start sweep

測試：

- `boundary_support_start = 43.3`
- `boundary_support_start = 43.4`
- `boundary_support_start = 43.5`

holdout 固定：

- `43.8 ~ 43.9`

輸出：

- `p3_6m20_m2_boundary_start_433_r16/`
- `p3_6m20_m2_boundary_start_434_r16/`
- `p3_6m20_m2_boundary_start_435_r16/`

### 結果

三組結果完全一致：

- selected restart seed = `7`
- `support_selection_pairwise_accuracy = 1.0`
- `LE-GRA utility = 0.579609048805`
- `teacher utility = 0.579609048805`
- `CQI utility = 0.579083105194`

也就是說：

- `LE-GRA` 在三個 boundary start 設定下都精準追平 teacher
- 而且都穩定優於 CQI baseline

### 解讀

這表示 `P3.6m-19` 不是因為剛好踩到 `43.4` 這個 magic number。

至少在 `43.3 ~ 43.5` 這個很小的 boundary 區間內：

- replay 機制是穩定的
- 不需要精準微調到某一個唯一閾值才生效

## B. holdout shift sweep

測試：

- `43.8 only`
- `43.9 only`
- `44.0 only`

boundary start 固定：

- `43.4`

輸出：

- `p3_6m20_m2_holdout_438_only_r16/`
- `p3_6m20_m2_holdout_439_only_r16/`
- `p3_6m20_m2_holdout_440_only_r16/`

### 結果

#### 43.8 only

- selected restart seed = `7`
- `LE-GRA utility = 0.579609048805`
- exact teacher match

#### 43.9 only

- selected restart seed = `7`
- `LE-GRA utility = 0.579609048805`
- exact teacher match

#### 44.0 only

- selected restart seed = `7`
- `LE-GRA utility = 0.629078111650`
- `CQI utility = 0.629078111650`
- `teacher utility = 0.629078111650`

### 解讀

這裡最重要的訊息有兩層：

第一層：

- `43.8` 和 `43.9` 各自單獨拿出來測，結果都成立
- 所以 `P3.6m-19` 的成功不是「兩個時間點平均起來剛好好看」
- 而是這兩個關鍵 holdout slice 各自都真的被救起來了

第二層：

- 到了 `44.0`，情況已經變了
- 這裡不是 `LE-GRA` 特別厲害
- 而是 `CQI` 本身就已經追平 teacher

所以 `44.0` 不應該被解讀成：

- learner 泛化得更遠了

比較準確的說法是：

- `44.0` 已經不是同一種「teacher 明顯優於 static baseline」的困難 regime

## 目前可以很有把握下的結論

### 結論 1：這不是單點巧合

最小版 boundary-aware support weighting 在 `m2` 上的成功，
已經通過第一輪 robustness check。

它不是：

- 只對 `43.4` 這一個數字有效
- 也不是只對 `43.8~43.9` 這個雙點平均有效

### 結論 2：有效範圍目前明確落在 43.8 / 43.9 這個 late-boundary 區段

在 `43.8`、`43.9` 這兩個 slice 上：

- `teacher > CQI`
- 而 replay 後的 `LE-GRA` 可以追平 teacher

這是目前最有價值的結論，因為它代表：

- learner 真正被推過了原本的錯誤 local rule

### 結論 3：44.0 是 regime change，不是同一個難題的延伸證據

`44.0` 上出現：

- `LE-GRA = CQI = teacher`

這不表示 learner 更強了，而表示：

- 這個點對 static baseline 已經不難

所以後續如果要繼續驗證 transfer，應該找的是：

- 仍然維持 `teacher > CQI`
- 但又靠近目前這個 late-boundary 區段的 slice

而不是把 `44.0` 當成更強的泛化證據。

## 對下一步的影響

這一輪 robustness check 做完後，我認為我們已經可以停止懷疑這件事：

- 「boundary-aware support weighting 到底是不是假訊號」

現在比較值得問的問題改成：

- 這個機制能不能 transfer 到別的、但仍然困難的 sibling regime？

所以最合理的下一步不是擴大矩陣，而是做一個很小的外部轉移驗證：

1. 找一個仍然滿足 `teacher > CQI` 的近鄰 regime
2. 套同一個最小 replay protocol
3. 看是否也能把 `LE-GRA` 往 teacher 拉近

## 一句話總結

`P3.6m-20` 證明了：

- `boundary-aware support weighting` 在 `m2` 的成功不是偶然
- 它在 `43.8/43.9` 這個真正困難的 late-boundary holdout 上是穩的
- 現在該做的不是回頭懷疑它，而是測它能不能 transfer 到下一個困難近鄰 regime
