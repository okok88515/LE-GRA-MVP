# P3.6q-24: 找到新的 dual-boundary temporal crossover regime，而且它真的能放大方法差距

## 這輪的目標

我們要找的不是另一個零碎 hard point，
而是一個更像 benchmark 的新 regime：

- teacher 穩定需要 split
- split 不只是一個瞬間
- `multi-feature k-means` 不容易剛好解掉
- `LE-GRA` 會出現有意義但不完全的追趕

這樣才有機會把方法差距穩定放大。

## 最後選到的 family

根據 source family ranking，最值得押注的 family 仍然是：

- `3|4|5|6 @ gnb_2`

我用這條 family 建了一個新的 spec：

- `p3_6q23_dual_boundary_crossover_spec.json`

並生成 bundle：

- `p3_6q23_dual_boundary_crossover_bundle/`

## 這個 regime 的設計重點

角色分工：

- `ue4`: persistent weak anchor
- `ue5`: early-phase secondary weak candidate
- `ue6`: late-phase secondary weak candidate
- `ue3`: strong anchor

設計意圖：

- 前段 teacher 應偏好 `ue4 + ue5`
- 後段 teacher 應偏好 `ue4 + ue6`
- `ue5` / `ue6` 在 snapshot feature 上不能太容易分
- 但 history / previous-quality / rb-scale 要提供足夠結構，讓 teacher 真正有 temporal crossover

## Teacher audit 結果

Artifact:

- `p3_6q23_teacher_audit/`

最重要結果：

- positive gain count = `19`
- positive segment count = `2`
- segment 1:
  - `25.8s ~ 27.0s`
  - length = `13`
- segment 2:
  - `28.3s ~ 28.8s`
  - length = `6`

而且這不是同一個 split 一直重複：

- early positive split:
  - `3|6 / 4|5`
- late positive split:
  - `3|5 / 4|6`

這代表我們真的做出想要的東西了：

- persistent weak anchor 還在
- secondary weak user 會隨時間切換
- teacher-positive corridor 不只是一個單點

## Focused learner probe

我接著做了一個最關鍵的 focused probe：

- train end = `27.0`
- test = `28.3 ~ 28.8`

也就是：

- 用早段 `{4,5}` 的 regime 訓練
- 測晚段是否能跟上 `{4,6}` crossover

Artifact:

- `p3_6q24_dual_boundary_crossover_temporal_probe/`

### 主結果

- `No grouping = 0.5721841780840183`
- `Multi-feature k-means = 0.5721841780840183`
- `Resource-cost k-means = 0.5790955890522329`
- `Offline teacher = 0.5790955890522329`
- `LE-GRA MVP = 0.5779436872241971`

## 為什麼這結果很重要

這條 regime 已經把差距拉出來了，而且方式很乾淨：

### 1. `teacher` 明顯優於 `no-group`

- gap 約 `0.0069`

這比很多之前「看起來都差不多」的情況更乾淨。

### 2. `multi-feature k-means` 完整失敗

在 test window `28.3 ~ 28.8`：

- teacher split = `3|5 / 4|6`
- `Multi-feature k-means` 一直輸出 single-group
- pairwise accuracy = `0.3333`
- ARI = `0`
- NMI = `0`

這非常關鍵，因為它表示：

- 這條新 regime 不會被 plain snapshot clustering 輕易解掉

### 3. plain `LE-GRA MVP` 已經有追上，但還沒有完全穩定

plain LE-GRA 的行為很漂亮，也很有研究價值：

- 在 `28.4 ~ 28.8` 的後 5 個 snapshots
  - 已經能輸出正確 split `4|6 / 3|5`
  - teacher imitation = `1.0`
- 但在 crossover 起點 `28.3`
  - 仍然塌成 single-group

所以這條 regime 的最佳描述不是：

- 完全學不起來

而是：

- LE-GRA 已經接近抓到 temporal crossover
- 但在最早的 boundary-switch snapshot 還不夠穩

## 為什麼這比 `o8` / `m4b` 更像下一個主力 regime

### 相比 `o8`

- `o8` 太短，幾乎是 single-point bridge case
- 這條新 regime 有 `6` 個 late positive snapshots

### 相比 `m4b`

- `m4b` 比較像固定 weak anchor + secondary weak closure
- 這條新 regime 多了一個真正的 secondary weak role switch

### 相比 `q10`

- `q10` 的核心更偏 selector / basin
- 這條新 regime 更偏 temporal crossover generalization

所以它補上了目前研究故事還缺的一塊：

- one regime where plain baselines fail hard,
- teacher-positive corridor is not a single point,
- and LE-GRA is close but not fully stable on the crossover boundary.

## 額外檢查：最小 bridge 沒有直接補掉它

我還補跑了：

- `p3_6q24_dual_boundary_crossover_anchor_probe/`
- `grouping_mode = candidate_anchor_hybrid`
- `restart_selection_mode = margin_aware`

結果：

- `LE-GRA MVP` 仍然是 `0.5779436872241971`
- 沒有直接回到 teacher match

這點很重要，因為它表示：

- 這條 regime 不像 `o8` / `m4b` 那樣可以被現有最小 bridge 直接補完
- 它更像一個真正值得繼續打的 next-step benchmark

## 目前最準確的高層結論

`p3_6q23 / q24` 這條線是目前最值得往下做的新 regime，因為它同時滿足三件事：

1. 有夠長的 teacher-positive corridor
2. `multi-feature k-means` 會穩定失敗
3. plain LE-GRA 已經部分成功，但在 crossover boundary 還不夠穩

換句話說，它不是：

- 太容易
- 也不是完全學不起來
- 而是剛好落在「最有機會做出下一個真正突破」的位置

## 我建議的下一步

如果要繼續往「更大的突破」前進，
我最推薦接著做這條：

1. 把 `28.3` 當成主 boundary failure 點
2. 專門設計：
   - boundary-aware supervision
   - 或 temporal support replay
   - 或 candidate switch calibration
3. 目標不是整段重做，
   而是先把 `28.3` 這個 earliest crossover snapshot 補起來

因為一旦 `28.3` 也補上，
這條 regime 就會從：

- "LE-GRA almost gets it"

變成：

- "LE-GRA can generalize an early-to-late secondary-weak crossover that plain baselines cannot handle"

這會是非常強的研究結果。
