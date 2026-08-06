# P3.6m-3 focused learner / ablation on the positive-family decoy regime

## 目的

`P3.6m-2` 首次做出同時具備以下兩點的 regime：

- `teacher` 仍然有正增益 split
- `ue 4` 被注入成第二個 decoy weak candidate

所以 `P3.6m-3` 的問題變成：

- 在這條新 regime 上，
  - `teacher`
  - `LE-GRA`
  - `multi-feature`
  - `CQI`
  - `resource-cost`
  - `no-group`

之間是否終於會拉開差距？

## 實驗設定

輸入 bundle：

- `p3_6m2_positive_family_decoy_bundle/bundle`

輸出：

- `p3_6m2_seg01_split437_temporal_learner/`

命令使用與舊 `seg_01` 相同的 temporal protocol：

- `focus_ue_ids = 0 1 15 2 3 4 5`
- `train_window_end = 43.7`
- `test_window = 43.8 ~ 43.9`
- `max_groups = 3`
- `epochs = 12`
- `feature_mode = history_cost_quality`
- `seed = 9`

這樣的好處是可以直接和舊的：

- `p3_6i2_seg01_split437_temporal_learner/`

做 apples-to-apples 比較。

## 資料切分

來自 `split_summary.json`：

- `background_train_scenarios = 150`
- `focus_train_scenarios = 527`
- `focus_test_scenarios = 2`
- `focus_train_positive_gain_count = 7`
- `focus_test_positive_gain_count = 2`

也就是說，test set 正好就是新 regime 的兩個正增益 snapshot：

- `43.8s`
- `43.9s`

## Main comparison

來自 `main_comparison.csv`：

### Offline teacher

- `utility = 0.579609048805`
- `system_SE = 25.396825`
- `average_quality = 3.428571`
- `avg_switching = 0.485714`
- `avg_groups = 2.0`

### LE-GRA / Multi-feature / CQI / Resource-cost

四者完全重合：

- `utility = 0.579083105194`
- `system_SE = 28.055556`
- `average_quality = 3.571429`
- `avg_switching = 0.514286`
- `avg_groups = 2.0`

### No grouping

- `utility = 0.547184178084`
- `system_SE = 16.666667`
- `average_quality = 3.0`
- `avg_switching = 0.4`
- `avg_groups = 1.0`

## 最重要結果

### 1. 差距終於被拉出來了

這次不再是：

- `teacher = LE-GRA = multi-feature`

而是：

- `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`

雖然差距還不大，但它是實質存在的：

- `teacher - LE-GRA = 0.0005259436115`

這代表：

- 新的 `P3.6m-2` regime 已經足以讓 `teacher` 和 learner/static baselines
  出現可觀察分離

### 2. 差距來自 split identity，不只是 groups 數量不同

在兩個 test snapshot 上，所有 grouping-aware 方法都預測 `2` 群。  
所以差距不是因為：

- 有沒有 split
- 或 split 成幾群

而是因為：

- **誰跟誰被放在同一群**

## Teacher vs predicted grouping

用 debug 重跑後確認：

### `43.8s`

Teacher：

- `[[0,1,3,4,6],[5,2]]`

對應原始 UE：

- 強組：`{0,1,2,3,5}`
- 弱組：`{4,15}`

LE-GRA / Multi-feature / CQI / Resource-cost：

- `[[0,1,3,4,5,6],[2]]`

對應原始 UE：

- 強組：`{0,1,2,3,4,5}`
- 弱組：`{15}`

### `43.9s`

結果完全相同。

## 這代表什麼

### Teacher 的判斷

Teacher 認為：

- `ue 15` 是真正 primary weak
- `ue 4` 也已經弱到值得和 `ue 15` 一起被抽出去

也就是說，teacher 接受了 `P3.6m-2` 注入的 decoy ambiguity。

### LE-GRA / Multi-feature 的判斷

LE-GRA 與所有 static baselines 仍然認為：

- 只有 `ue 15` 應該被 isolate
- `ue 4` 還不該進弱組

所以現在的錯誤模式非常清楚：

- learner 不是沒學會 split
- learner 是**沒有學到 decoy candidate 也該進弱組**

## Teacher-imitation diagnostics

來自 `teacher_imitation_diagnostics.csv`：

- `pairwise_accuracy = 0.714285714286`
- `ARI = 0.416666666667`
- `NMI = 0.428140178120`

對 `Multi-feature k-means` 與 `LE-GRA MVP` 都相同，兩個 snapshot 也相同。

這再次說明：

- `LE-GRA` 目前還沒有超過 `multi-feature`
- 但它也沒有退化到 `no-group`
- 它現在卡在和 static grouping 一樣的錯誤 split identity 上

## 與舊 seg_01 的直接比較

舊的 `p3_6i2_seg01_split437_temporal_learner` 結果是：

- `teacher = LE-GRA = multi-feature = CQI = resource-cost`

新的 `P3.6m-3` 結果變成：

- `teacher > LE-GRA = multi-feature = CQI = resource-cost`

所以 `P3.6m-2` 的 decoy 注入確實做到了原本想要的事：

- 不是把 `teacher - no-group` 變得特別大
- 而是讓 `teacher` 的 split 結構不再被 static / learner 完全複製

## 結論

`P3.6m-3` 是目前最重要的一個 learner-side evidence point，因為它首次證明：

1. 在正增益 teacher regime 上
2. 注入第二個 decoy weak candidate 之後
3. `teacher` 和 `LE-GRA / multi-feature` 會做出不同 split decision

這是到目前為止最接近研究主張核心的結果：

- teacher 用更細的歷史/效用結構做判斷
- static feature clustering 與目前 learner 還無法完全複製

## 下一步建議

現在最合理的後續不是再回去盲目換 family，而是直接沿著這條 regime 做：

1. `P3.6m-4`: 在 `43.7~43.9` 周圍再複製 2 到 3 個相似 temporal slice
   - 看這個分歧是否能從單一 segment 變成可重複 evidence
2. `P3.6m-5`: 針對 learner 端做 supervision redesign
   - 強化對「secondary weak candidate」的判別
   - 檢查是否能讓 LE-GRA 超過 multi-feature
