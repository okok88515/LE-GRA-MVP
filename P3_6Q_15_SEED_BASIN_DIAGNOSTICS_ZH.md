# P3.6q-15: q10 seed basin diagnostics point to a restart-selection bottleneck

## 背景

在 `P3.6q-14` 我們已經確認：

- `q10` 的成敗不只是 grouping mode 問題
- `seed 9` 是失敗 basin
- `seed 11` 是成功 basin

這一輪的目標不是再做新 tweak，而是回答一個更根本的問題：

- 目前的 restart selection 到底有沒有把我們帶到錯的 basin？

## 比較對象

聚焦 plain learner：

- `p3_6q10_plain_baseline_275/`
  - restart seeds = `7|9|11`
  - selected restart seed = `9`
- `p3_6q10_plain_baseline_275_seed11/`
  - restart seed forced to `11`

固定 regime：

- bundle: `p3_6q10_six_user_transition_extension_bundle/bundle`
- train end = `27.5`
- test = `27.6 ~ 28.2`

## 直接結果

### 被 selector 選中的 seed 9

- `LE-GRA MVP = 0.6186215935418201`
- 平均 `pairwise / ARI / NMI = 0.6952 / 0.4286 / 0.4286`

測試區段行為：

- `27.6s`: 正確 split
- `27.7s ~ 28.0s`: collapse 成 single-group
- `28.1s ~ 28.2s`: 再次回到正確 split

### 沒被 selector 選中的 seed 11

- `LE-GRA MVP = 0.6368533564947124`
- 平均 `pairwise / ARI / NMI = 1.0 / 1.0 / 1.0`

測試區段行為：

- `27.6s ~ 28.2s` 全部都是正確 split

## 支持集 selection 指標

來自 `restart_candidates.csv`：

| Seed | support pairwise | support ARI | support NMI | weak margin min | weak margin mean | proto sep margin | selected |
|---|---:|---:|---:|---:|---:|---:|---|
| 7  | 0.9502 | 0.9253 | 0.9253 | 0.0103 | 0.0283 | 0.4033 | no |
| 9  | **0.9617** | **0.9425** | **0.9425** | **-0.0170** | **-0.0055** | **0.2877** | yes |
| 11 | 0.9579 | 0.9368 | 0.9368 | 0.0122 | 0.0180 | 0.3624 | no |

這裡最重要的反差是：

- `seed 9` 在 support pairwise / ARI / NMI 上略高，所以被選中
- 但它的 weak margin min / mean 是負的，而且 prototype separation 也是三者最差
- `seed 11` 雖然 support imitation 指標稍低，卻有更健康的 weak margin 與 separation，最後在 focus-test 完全泛化成功

## focus-test 分岔細節

整理在：

- `p3_6q10_seed_basin_focus_test_comparison.csv`

關鍵片段：

| time | teacher candidate | seed 9 top-k | seed 11 top-k | seed 9 grouping | seed 11 grouping |
|---|---|---|---|---|---|
| 27.6 | `2|6` | `5|1` | `5|6` | correct | correct |
| 27.7 | `2|6` | `5|1` | `2|5` | collapse | correct |
| 27.8 | `2|6` | `5|1` | `2|5` | collapse | correct |
| 27.9 | `2|6` | `5|3` | `2|5` | collapse | correct |
| 28.0 | `2|6` | `5|3` | `2|5` | collapse | correct |
| 28.1 | `2|6` | `5|3` | `2|5` | correct | correct |
| 28.2 | `2|6` | `5|1` | `2|5` | correct | correct |

## 最重要 insight

### 1. success basin 並不需要正確的 weak top-k

`seed 11` 的 `predicted_topk_signature` 也不是 teacher 的 `2|6`：

- `27.6`: `5|6`
- `27.7 ~ 28.2`: `2|5`

但它的 final grouping 仍然全部正確。

這代表：

- 在 plain learner 的成功 basin 裡，final embedding geometry 已經足以讓 `kmeans_embedding` 形成 teacher-equivalent split
- weak top-k audit 很有參考價值，但它不是唯一決定因子

### 2. failure basin 的問題比較像 grouping instability，而不是單純 candidate miss

`seed 9` 的 top-k 當然也不對，但更重要的是：

- 它在 `27.7 ~ 28.0` 這段明顯失去雙群穩定性
- collapse 完之後，`28.1 ~ 28.2` 又能回到正確 split

這看起來不像整段都學壞，而比較像：

- 在 boundary corridor 中缺乏穩定的 split margin

### 3. 目前的 restart selector 很可能偏向 imitation-overfit basin

現在的 selector 主要根據 support-set 的：

- pairwise accuracy
- ARI
- NMI
- utility gap

但 `q10` 顯示出一個新問題：

- 在 support imitation 上更高，不代表 boundary generalization 更好

更尖銳地說：

- `seed 9` 被選中，不是因為它真的更穩
- 而是因為目前的 selection criterion 還看不見那個 `27.7 ~ 28.0` 的脆弱 corridor

## 研究意義

這個結果把問題再往前推了一步。

我們現在不應該只問：

- learner 能不能找到 teacher candidate？
- grouping bridge 能不能補最後一哩？

還要加上一個更前面的問題：

- restart selection 能不能選到真正可泛化的 basin？

所以 `q10` 目前最完整的三層故事其實是：

1. basin selection
2. candidate / representation quality
3. final grouping construction

## 最值得做的下一步

我認為接下來最值得做的不是大 sweep，而是小而精準的 selector-side validation：

1. 做 `boundary-aware restart diagnostics`
   - 針對每個 restart seed，抽 teacher-positive / boundary-near 的 support subset
   - 比較誰在這些 corridor 上的 split margin 更穩
2. 如果訊號成立，再做最小版 restart selector 改寫
   - 不要重做整個 learner
   - 只調整 seed ranking
   - 讓 weak margin / prototype separation / boundary-support evidence 能參與 selection

## 目前結論一句話

`q10` 現在最像的不是「還缺一個 grouping tweak」，而是：

- 我們已經知道 repo 裡存在會成功的 basin，
- 但目前的 restart selector 可能會把它錯過。
