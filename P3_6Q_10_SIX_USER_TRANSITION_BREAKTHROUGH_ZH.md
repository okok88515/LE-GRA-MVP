# P3.6q-10: six-user transition pivot created a real bridge-needed regime

## 為什麼要做 q-10

在 `q8` 與 `q9` 之後，我們已經確認：

- `3|4|5|6 @ gnb_2` 雖然可以被延長成更長的 teacher-positive bridge
- 但那條 bridge 仍然太容易
- `Resource-cost k-means`、`Multi-feature k-means` 甚至 plain LE-GRA
  都已經能跟上 teacher

所以 `q10` 不再沿用那條 family，而是正式 pivot 到：

- `1|2|3|4|5|6 @ gnb_2`

原因是它在 `rb_028` 下本來就有一個很有價值的自然結構：

- `27.3`: teacher isolate `ue2`
- `27.4 ~ 27.6`: teacher 切成 `{ue2, ue6}` dual-weak group

這種「單弱轉雙弱」的 transition，比前一條 family 更有機會變成真正的
bridge-needed regime。

## 實作

新增：

- `p3_6q10_six_user_transition_extension_spec.json`

輸出：

- `p3_6q10_six_user_transition_extension_bundle/`
- `p3_6q10_teacher_audit/`
- `p3_6q10_focus_mining/`
- `p3_6q10_kmeans_learner/`
- `p3_6q10_hybrid_learner/`
- `p3_6q10_membership_order_learner/`

設計原則：

1. 保留原始 `ue2 -> {ue2, ue6}` 的 natural transition
2. 把 `27.7+` 原本會 collapse 的區間延長成真正的 positive corridor
3. 加入 history-aware conflict，使這條 corridor 不再像 snapshot singleton
   那麼好解

## Teacher 結果

Family `1|2|3|4|5|6 @ gnb_2` 的正增益片段為：

- `27.3`
  - `[[0,2,3,4,5],[1]]`
  - isolate `ue2`
  - gain = `0.060380914957876564`
- `27.4 ~ 27.6`
  - `[[0,2,3,4],[1,5]]`
  - weak group = `{ue2, ue6}`
  - gain = `0.16083185759435376`
- `27.7 ~ 28.2`
  - `[[0,2,3,4],[1,5]]`
  - weak group 仍維持 `{ue2, ue6}`
  - gain = `0.03190558516756159`

這個結果的意義很大：

1. teacher-positive corridor 從原本只到 `27.6`，成功延長到了 `28.2`
2. 中段 gain 直接放大到 `0.1608`
3. 晚段雖然 gain 下降，但沒有 collapse 回 single-group

也就是說，`q10` 不只是延長，而是第一次在新 family 上成功造出更長的
dual-weak regime。

## Focused learner 結果

設定：

- focus family = `1|2|3|4|5|6`
- train end = `27.6`
- test = `27.7 ~ 28.2`

### 1. `kmeans_embedding`

- `No grouping` = `0.6138508447506849`
- `CQI k-means` = `0.6244860398065387`
- `Resource-cost k-means` = `0.6298036373344656`
- `Multi-feature k-means` = `0.6138508447506849`
- `Offline teacher` = `0.6457564299182464`
- `LE-GRA MVP` = `0.6244860398065387`

重點：

- plain LE-GRA 沒有 match teacher
- 它只追到和 `CQI k-means` 相同的層級

### 2. `hybrid_membership_kmeans`

- `Offline teacher` = `0.6457564299182464`
- `LE-GRA MVP` = `0.6457564299182464`

重點：

- hybrid bridge 成功追回 teacher
- 而且明顯優於：
  - `CQI k-means`
  - `Resource-cost k-means`
  - `Multi-feature k-means`
  - plain `kmeans_embedding`

### 3. `membership_order`

- `Offline teacher` = `0.6457564299182464`
- `LE-GRA MVP` = `0.6457564299182464`

重點：

- 這代表這次的突破核心，不一定是 embedding k-means 本身
- 更像是 weak-membership ordering / bridge inference path 已經足夠把
  正確 split 撈回來

## 研究結論

`q10` 是目前 `P3.6q` 最重要的一次突破，因為它同時滿足三件事：

1. teacher corridor 真的被延長
2. plain snapshot / clustering baselines 拉不回 teacher
3. membership-aware inference path 可以追回 teacher

換句話說，這是目前少數真正出現：

- `teacher > resource-cost kmeans`
- `teacher > plain LE-GRA`
- `hybrid / membership-aware LE-GRA = teacher`

的 focused regime。

## 對下一步的意義

下一步最值得做的不是再換 family，而是沿著 `q10` 做 focused mechanism
study：

1. 檢查為什麼 `membership_order` 已足夠追回 teacher
2. 做 weak-group prediction / candidate ranking audit
3. 比較 plain kmeans path 到底錯在哪裡
4. 再決定是否需要把這條 regime 進一步放大成更長、更多 seed 的主結果
