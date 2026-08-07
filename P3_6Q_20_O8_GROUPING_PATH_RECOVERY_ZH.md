# P3.6q-20: `o8` 不是 learner 表示失敗，而是 LE-GRA grouping path 失敗；anchor bridge 可直接補回

## 背景

在 `P3.6q-17` 我們曾把 `o8` 暫時歸類成：

- selector 換了也沒用
- 比較像 downstream inference / grouping bottleneck

這個方向其實沒有錯，但現在可以更精確。

因為在新的 focused check 中：

- `margin_aware + candidate_anchor_hybrid`
- 在 `o8` 上也達成了 full teacher match

所以這一輪的任務，是把 `o8` 的真正機制講清楚。

## 兩個對照 run

### 舊 run

- `p3_6q16_o8_margin_selector/`
- `restart_selection_mode = margin_aware`
- `grouping_mode = kmeans_embedding`

結果：

- selected restart seed = `7`
- `Offline teacher = 0.6198214236671593`
- `Multi-feature k-means = 0.6198214236671593`
- `LE-GRA MVP = 0.6071841780840183`

也就是：

- 同一個模型、同一個 seed
- baseline `Multi-feature k-means` 已經能 match teacher
- 只有 `LE-GRA MVP` 自己的 grouping path 塌成 single-group

### 新 run

- `p3_6q20_o8_anchor_closure_margin_selector/`
- `restart_selection_mode = margin_aware`
- `grouping_mode = candidate_anchor_hybrid`

結果：

- selected restart seed 仍然是 `7`
- `Offline teacher = 0.6198214236671593`
- `LE-GRA MVP = 0.6198214236671593`

所以：

- 不是 seed 換了才成功
- 不是 learner 重新學到新表示才成功
- 而是 final grouping path 被修正了

## 關鍵 diagnostics

在 test snapshot `18.7s`：

- teacher candidate signature = `3|4`
- predicted top-k signature = `3|4`
- predicted top-1 weak UE = `3`
- predicted top-2 weak UE = `4`

舊 run 的 teacher imitation diagnostics：

- teacher grouping = `0|1|2 / 3|4`
- `Multi-feature k-means` predicted = `0|1|2 / 3|4`
- `LE-GRA MVP` predicted = `0|1|2|3|4`

新 run 的 teacher imitation diagnostics：

- teacher grouping = `0|1|2 / 3|4`
- `LE-GRA MVP` predicted = `3|4 / 0|1|2`

結論非常直接：

- `o8` 的 candidate path 本來就對
- embedding space 也足以讓 plain multi-feature k-means 分對
- 真正錯的是 LE-GRA 原本的 final grouping construction
- `candidate_anchor_hybrid` 直接把這條 grouping path 修回 teacher-equivalent split

## 修正後的研究解讀

`o8` 不該再被描述成「單純 selector 無法幫忙的 hard regime」。

更準確地說，它是：

- not selector-dominated
- not learner-representation-dominated
- it is a **LE-GRA-specific grouping-path failure**

而且它和 `m4b` 的共同點比先前想像得更強：

- 兩者都不是 candidate discovery 問題
- 兩者都能被 anchor-preserving grouping bridge 補回

但兩者仍有差別：

- `m4b`：
  - 先要靠 better basin / better selector
  - 再要補 secondary weak closure
- `o8`：
  - selected seed 沒變
  - 直接是 LE-GRA grouping path 本身的問題

## 對整體研究的意義

這讓目前的 hard-regime taxonomy 更完整：

1. selector-dominated failure
   - `q10`
2. post-selector weak-closure failure
   - `m4b`
3. LE-GRA-specific grouping-path failure even when candidate/top-k is already right
   - `o8`

但更高層地看，`m4b` 和 `o8` 其實都支持同一個訊息：

- 一旦 weak candidate path 已經恢復
- anchor-preserving grouping bridge 會變成非常有力的最後一哩修正

## 建議下一步

現在最值得做的，不是立刻擴大所有 matrix，
而是先把這個新判準整理清楚：

- 什麼時候 regime 已經滿足「candidate path recovered」？
- 一旦滿足，`candidate_anchor_hybrid` 是否應該成為優先測試的 structural bridge？

換句話說，下一步應該是：

- 做一個小型 regime checklist / decision rule
- 幫我們快速判斷：
  - 先救 selector
  - 還是直接測 anchor-preserving closure
