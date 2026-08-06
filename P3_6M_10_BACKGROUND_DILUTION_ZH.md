# P3.6m-10 background dilution / support efficiency

## 背景

`P3.6m-9` 已經找到一個很清楚的 evidence-density threshold：

- `focus_train_repeat = 1, 2`
  - LE-GRA 仍卡在舊解
- `focus_train_repeat >= 4`
  - LE-GRA 直接對齊 teacher

但這還留下一個重要問題：

**是 exact support 本身真的不夠，還是它只是被大量 background train scenarios 淹掉了？**

## 核心想法

如果主因是 background dilution，那麼：

- 不增加 support 數量
- 只降低背景資料量

也可能讓 `focus_train_repeat = 2` 跨過 threshold。

這比單純 brute-force replay 更接近「support-efficient curriculum」。

## protocol 改動

在 `run_p3_6g_temporal_learner.py` 新增：

- `--background-train-limit`

用 deterministic subsampling 限制 background train scenarios 數量，
而不改 focus support slice 本身。

另外也補了一個可重跑的 sweep 腳本：

- `run_p3_6m10_background_dilution_sweep.py`

## 主 sweep 設定

固定：

- support window: `43.7s ~ 43.8s`
- holdout test: `43.9s`
- `focus_train_repeat = 2`
- learner recipe 同 `P3.6m-9`

掃：

- `background_train_limit ∈ {150, 100, 50, 20, 10, 5, 0}`

頛詨：

- `p3_6m10_background_dilution_sweep/`
- summary: `p3_6m10_background_dilution_sweep/sweep_summary.csv`

## 主 sweep 結果

| background limit | effective background | effective focus support | LE-GRA utility | teacher gap | pairwise | ARI | NMI |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 150 | 150 | 4 | 0.579083 | 0.000526 | 0.714 | 0.417 | 0.428 |
| 100 | 100 | 4 | 0.579083 | 0.000526 | 0.714 | 0.417 | 0.428 |
| 50 | 50 | 4 | 0.579609 | 0.000000 | 1.000 | 1.000 | 1.000 |
| 20 | 20 | 4 | 0.579609 | 0.000000 | 1.000 | 1.000 | 1.000 |
| 10 | 10 | 4 | 0.579609 | 0.000000 | 1.000 | 1.000 | 1.000 |
| 5 | 5 | 4 | 0.579609 | 0.000000 | 1.000 | 1.000 | 1.000 |
| 0 | 0 | 4 | 0.579609 | 0.000000 | 1.000 | 1.000 | 1.000 |

## 初步結論

這個結果非常關鍵：

- `focus_train_repeat = 2` 並不是天生不夠
- 它是在 background 太多時被淹掉

換句話說：

**P3.6m-9 的 threshold，並不只是「需要更多 support」，而是「需要足夠高的 support-to-background ratio」。**

## boundary refinement

為了判斷是 ratio 還是 absolute support 比較重要，又補了幾個關鍵點：

- `repeat = 3, background = 150`
- `repeat = 2, background = 80`
- `repeat = 2, background = 75`
- `repeat = 2, background = 60`

頛詨：

- `p3_6m11_repeat3_bg150/`
- `p3_6m11_repeat2_bg080/`
- `p3_6m11_repeat2_bg075/`
- `p3_6m11_repeat2_bg060/`

### refinement 結果

- `repeat = 3, bg = 150`
  - 成功，LE-GRA 對齊 teacher
- `repeat = 2, bg = 80`
  - 失敗
- `repeat = 2, bg = 75`
  - 失敗
- `repeat = 2, bg = 60`
  - 成功

## 更精準的解讀

這些點合起來看，比較像是 ratio threshold，而不是單一絕對 support 數量：

- `repeat = 2, bg = 75`
  - ratio = `4 / 75 ≈ 5.3%`
  - 失敗
- `repeat = 2, bg = 60`
  - ratio = `4 / 60 ≈ 6.7%`
  - 成功
- `repeat = 3, bg = 150`
  - ratio = `6 / 150 = 4.0%`
  - 成功

這表示真正的控制變數不一定是單純比例，也可能同時受：

- exact support slice 數量
- support/background ratio
- support 在 schedule 中的出現頻率

共同影響。

但至少可以很明確地說：

**背景 dilution 是真的，而且它足以解釋為什麼 `repeat = 2` 在原 protocol 下失敗。**

## 到目前為止最重要的研究結論

把 `P3.6m-8 ~ P3.6m-10` 連起來，現在可以更清楚地描述 bottleneck：

1. LE-GRA 並非學不會 secondary weak candidate `{ue4}`
2. 目前問題主要不是 architecture impossibility
3. 真正的問題是：
   - exact dual-weak support density 不足
   - 再加上 background dilution
   - 導致 learner 落回只 isolate `ue15` 的局部解

## 建議下一步

最合理的下一步不是立刻重生資料，而是做：

1. support-efficient schedule design
   - 不增加 unique support slice 數量
   - 直接在 `train_trace_model` 或 temporal protocol 中做 smarter curriculum

2. ratio-aware training schedule
   - 例如固定每個 epoch 中 exact support slice 的最小占比
   - 而不是單純用整體資料量自然混合

3. 之後再決定是否需要新的 family 或新資料
   - 若 support-efficient curriculum 仍然不穩
   - 再考慮擴 bundle / 重生資料
