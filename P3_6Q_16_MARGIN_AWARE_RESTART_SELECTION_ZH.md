# P3.6q-16: minimal margin-aware restart selection recovers q10 without changing the learner

## 動機

`P3.6q-15` 已經指出一個很明確的問題：

- repo 裡其實存在會成功的 basin
- 但目前的 restart selector 偏向 support imitation 指標
- 這會把 `seed 9` 這種 support 分數略高、但 boundary generalization 較差的 basin 選出來

所以這一步不是改 learner，也不是再做新的 supervision tweak，而是做一個最小 selector-side 驗證：

- 如果把 `weak margin` 和 `prototype separation` 放進 restart ranking，能不能把成功 basin 選出來？

## 實作

檔案：

- `run_p3_6g_temporal_learner.py`

新增參數：

- `--restart-selection-mode support_imitation`
- `--restart-selection-mode margin_aware`

其中：

- `support_imitation` 保持原本邏輯
- `margin_aware` 先比：
  - `support_weak_margin_min`
  - `support_weak_margin_mean`
  - `support_proto_sep_margin`
- 再比：
  - `support_pairwise_accuracy`
  - `support_ari`
  - `support_nmi`
  - `support_utility`
  - `selection_validation_loss`

## Focused validation A: plain q10 shifted-boundary

Command concept:

- same as `p3_6q10_plain_baseline_275`
- only add `--restart-selection-mode margin_aware`

Artifact:

- `p3_6q10_plain_baseline_275_margin_selector/`

Result:

- selected restart seed: `11`
- `LE-GRA MVP = 0.6368533564947124`
- `Offline teacher = 0.6368533564947124`

也就是說：

- 不改 learner
- 不改 grouping mode
- 不加 supervision
- 只改 restart selection

就能把原本 plain q10 shifted-boundary failure 直接修回 full teacher match。

## Focused validation B: localized q10 shifted-boundary

Command concept:

- same as `p3_6q10_kmeans_candidate_boundary_frontier_275`
- only add `--restart-selection-mode margin_aware`

Artifact:

- `p3_6q10_kmeans_candidate_boundary_frontier_275_margin_selector/`

Result:

- selected restart seed: `7`
- `LE-GRA MVP = 0.6368533564947124`
- `Offline teacher = 0.6368533564947124`

這個結果更有意思：

- margin-aware selector 不只會挑出 `11`
- 在 localized supervision 下，它甚至挑出另一個原本沒被選中的成功 basin `7`

## 最重要結論

### 1. q10 的 plain failure 並不是 learner capacity 不夠

因為現在 plain setting 下：

- learner 本身沒變
- inference `grouping_mode` 也沒變
- 只是 selector 換掉

結果就從：

- `0.6186`

變成：

- `0.6369`

這非常強烈地說明：

- 原本的主問題之一就是 basin selection

### 2. 目前 selector 真的會錯過更可泛化的 basin

原 selector 選：

- `seed 9`

margin-aware selector 選：

- plain: `seed 11`
- localized: `seed 7`

而且後兩者都在 focus-test 達到完整 teacher match。

這代表：

- 目前不是「只有一個 lucky seed」
- 而是「存在多個成功 basin，但原 selector 沒把它們排前面」

### 3. q10 的故事比原本簡單了一些

先前我們的敘事是：

1. localized supervision 修 candidate path
2. candidate-anchored grouping 修 final grouping

現在要加上更前面的一層：

1. restart selector 選 basin
2. learner / supervision 決定表示結構
3. grouping path 決定最後 split transfer

而且在 plain q10 shifted-boundary 上，這一步甚至顯示：

- 只要 basin 選對，plain `kmeans_embedding` 就已經足夠

## 對後續研究的意義

這個結果很重要，因為它讓我們少走很多冤枉路。

如果不先修 selector，我們很容易把：

- basin 選錯造成的 failure

誤判成：

- learner 架構不夠
- supervision 設計不夠
- grouping bridge 不夠強

換句話說，`q10` 已經明確證明：

- restart selection is a first-class research lever in this prototype

## 目前的保守判讀

雖然結果很強，但現在還不能直接把 `margin_aware` 當作最終答案全面推廣，因為：

- 這還只在 `q10` focused regime 做驗證
- 尚未檢查它在其他 regime 會不會挑到奇怪 basin

所以最合理的下一步不是大改主流程，而是：

1. 先把 `margin_aware` 當成 experimental selector
2. 在少數代表性 regime 上做 controlled transfer check
   - `q10`
   - `o8`
   - `m4b`
   - 一個 easy regime
3. 確認它是不是：
   - truly better selector
   - 還是只在 `q10` 特別有效

## 一句話結論

`q10` 現在第一次清楚顯示：

- 我們很多看起來像 learner failure 的問題，其實是 selector 先把我們帶進了錯的 basin。
