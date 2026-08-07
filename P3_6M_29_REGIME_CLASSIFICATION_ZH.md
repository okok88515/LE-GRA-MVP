# P3.6m-29 focused regime classification after phase-2 transfer

交接日期：2026-08-07

## 這一步的目的

做到 `P3.6m-28` 之後，我們其實已經不缺單點結果了。

現在更重要的是把目前手上的 focused regimes 做出結構化分類：

1. 哪些 regime 本來就容易，舊方法就能解
2. 哪些 regime 真的需要新的 bridge 才能解
3. 哪些 regime 到現在其實還沒有被證明是新的未解瓶頸

這份分類的價值在於：

- 之後不會再把時間浪費在已知容易的 regime 上反覆微調
- 也不會把 `m4b` 的突破誤解成「整個問題都解了」
- 能更清楚定義下一步到底要擴展什麼

## 本次分類依據

這次只使用目前最有代表性的 focused results：

### `m2` 系列

- `p3_6m20_m2_holdout_438_only_r16/`
- `p3_6m20_m2_holdout_439_only_r16/`
- `p3_6m28_m2_localized_hard_negative_membership_order/`

### `m4b` 系列

- `p3_6m21_m4b_boundary_weighting_transfer_r16/`
- `p3_6m25_m4b_minimal_joint_supervision_v1/`
- `p3_6m26_m4b_localized_hard_negative_v1/`
- `p3_6m26b_m4b_localized_hard_negative_membership_order/`
- `p3_6m27a_m4b_localized_membership_437_only/`
- `p3_6m27b_m4b_localized_membership_438_only/`
- `p3_6m27c_m4b_localized_membership_439_only/`

## 分類表

### A. Easy / already-solvable regime

代表：

- `m2`

證據：

- 在 `p3_6m20_m2_holdout_438_only_r16/`
- 以及 `p3_6m20_m2_holdout_439_only_r16/`

就算還是用舊的：

- `grouping_mode = kmeans_embedding`
- `pair_sampling = random_balanced`
- `supervision_weight_mode = uniform`

也已經有：

- `Offline teacher = 0.579609048805`
- `LE-GRA MVP = 0.579609048805`

也就是說：

- `m2` 不需要 localized hard negatives
- `m2` 也不需要 `membership_order` bridge
- 舊路徑本身就已經足以達到 teacher

`P3.6m-28` 再進一步證明：

- 即使把新方法搬到 `m2`
- `LE-GRA` 仍然維持 `0.579609048805`
- 而且 holdout weak-group audit 也能對上 `15|4`

所以目前對 `m2` 最準確的描述不是「新方法幫它解掉」，
而是：

- `m2` 是已解 regime
- 新方法能 transfer 進來且不退化

### B. Bridge-needed regime

代表：

- `m4b`

證據非常完整：

1. 在 `p3_6m21_m4b_boundary_weighting_transfer_r16/`
   - replay / support-side imitation 已經足夠強
   - 但：
   - `teacher = 0.579609048805`
   - `LE-GRA = 0.579083105194`

2. 在 `p3_6m25_m4b_minimal_joint_supervision_v1/`
   - 加入最小 joint supervision
   - 仍然：
   - `teacher = 0.579609048805`
   - `LE-GRA = 0.579083105194`

3. 在 `p3_6m26_m4b_localized_hard_negative_v1/`
   - 加入 localized hard negatives 後
   - utility 仍然不動：
   - `teacher = 0.579609048805`
   - `LE-GRA = 0.579083105194`
   - 但 weak-group ranking 已修正

4. 在 `p3_6m26b_m4b_localized_hard_negative_membership_order/`
   - 只把 inference 換成 `membership_order`
   - 立刻變成：
   - `teacher = 0.579609048805`
   - `LE-GRA = 0.579609048805`

5. 在 `p3_6m27a/b/c`
   - `43.7`
   - `43.8`
   - `43.9`
   三個 single-point holdout 都 individually match teacher

所以 `m4b` 的核心判讀非常清楚：

- 它不是 learner 完全學不到
- 而是 learner 修好的 weak frontier，舊的 `embedding -> kmeans` 路徑吃不到
- 因此它是一個典型的 bridge-needed regime

### C. Still-unspecified / not yet a confirmed new unsolved regime

目前其實沒有第三條已經被 focused 驗證、而且明確屬於「新的未解 hard regime」的 family。

這一點很重要。

因為如果現在貿然說「還有很多未解 regime」，
那其實不是被結果支持的結論。

目前更準確的說法是：

- 我們已明確辨識出：
  - 一條 easy regime：`m2`
  - 一條 bridge-needed regime：`m4b`
- 但還沒有第三條新的 focused regime 被完整挖出並驗證

也就是說，現在真正缺的不是更多 learner 微調，
而是更多有代表性的 regime discovery / regime mining。

## 到目前為止最重要的研究理解

### 1. 不是所有 dual-weak 外觀都一樣難

從 `m2` 和 `m4b` 的對照可以看到：

- 有些 regime 看起來也在 late threshold 附近
- 但其實舊方法已足夠

所以不能把所有 late-stage positive family 都當成同一種難題。

### 2. 現在真正被驗證的困難型態是 inference mismatch

在 `m4b` 上，最有價值的發現不是某個 loss 多加了幾分，
而是：

- weak frontier 已可被 learner 修正
- 但若最終 grouping 仍走 `kmeans_embedding`
- utility 依然會卡在 `CQI` plateau

這讓問題從模糊的「模型不夠強」，
收斂成更具體的：

- local supervision learned
- but final grouping path ignores that signal

### 3. 下一步最值得做的不是再磨 `m2` 或 `m4b`

因為：

- `m2` 已解
- `m4b` 也已有一條可重現的 teacher-matching path

所以後續最有資訊量的事情，應該是：

1. 找新的 focused family
2. 看它屬於：
   - easy
   - bridge-needed
   - genuinely unsolved
3. 再決定要不要升級成更一般化的 structure-level redesign

## 建議的下一步

最合理的下一步，不是擴大 seed 或 matrix，而是做：

### Step 1. regime mining

從 family bank 或既有 focused mining 結果中，找新的候選 family，優先找：

- teacher 明顯優於 baselines
- 而且有多個連續時間點，不是單一孤點
- 最好能觀察到明確的 dual-weak 或 multi-weak 候選結構

### Step 2. quick triage

對每個候選 family 先做最小 triage：

1. 舊 `kmeans_embedding` 是否已可對齊 teacher？
2. 如果不行，`membership_order` 是否就夠？
3. 如果還不行，再判定它是不是新的 genuinely unsolved regime

### Step 3. 只有找到新的 genuinely unsolved regime，才值得做更大改版

如果還沒找到新的未解 regime 就先做大幅模型改造，
很容易再次掉回：

- tweak 很多
- 但其實只是在已知 plateau 周圍兜圈

## 小結

目前最乾淨的分類是：

- `m2`：easy / already-solvable
- `m4b`：bridge-needed
- 其他：尚未被 focused 驗證成新的未解 regime

這代表現在研究最缺的不是更多 isolated tweaks，
而是新的高資訊量 regime discovery。
