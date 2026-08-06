# P3.6d Teacher-Decision Audit

更新日期：2026-08-06

## 這一輪做了什麼

新增腳本：

- `run_p3_6_teacher_decision_audit.py`

輸出目錄：

- `p3_6_teacher_audit/full_bundle/`
- `p3_6_teacher_audit/learner_test_split/`

這個 audit 直接量化 offline teacher 在真實 coupled trace 上的決策分布，重點不是 learner，
而是問一個更前面的問題：

> teacher 到底有沒有真的碰到「需要拆群」的 snapshot？

## 稽核範圍

### 1. Full bundle

- 場景數：`614`
- 使用全部 UE 做 snapshot-level audit

### 2. Learner test split

- 場景數：`311`
- 使用第一輪 learner 的 test UE：`0, 16, 2`

## 核心結論

### 1. Full bundle 幾乎永遠是單群組

`p3_6_teacher_audit/full_bundle/summary.csv`

- `scenario_count = 614`
- `multi_group_count = 1`
- `multi_group_ratio = 0.00163`
- `mean_teacher_group_count = 1.00163`
- `max_teacher_group_count = 2`
- `positive_gain_count = 0`
- `positive_gain_ratio = 0.0`

這代表：

- 614 個 snapshot 裡，只有 1 個被 teacher 切成超過 1 群
- 但連這 1 個案例，相對單群組也沒有真正的 utility 提升

### 2. Learner test split 完全沒有多群組案例

`p3_6_teacher_audit/learner_test_split/summary.csv`

- `scenario_count = 311`
- `multi_group_count = 0`
- `multi_group_ratio = 0.0`
- `mean_teacher_group_count = 1.0`
- `positive_gain_count = 0`

也就是說，第一輪 learner test set 上，teacher 100% 都是單群組。

這就直接解釋了前一輪 learner 為什麼：

- 六個方法結果完全一樣
- `pairwise_accuracy = 1.0`
- `ARI = 1.0`
- `NMI = 1.0`

因為 teacher 本身就沒有提供任何「需要拆群」的 supervision diversity。

## 關鍵切面結果

### 1. 按 user_count 看

`p3_6_teacher_audit/full_bundle/by_user_count.csv`

- 2-user：`231` 個，`0` 個多群組
- 3-user：`75` 個，`0` 個多群組
- 4-user：`61` 個，`0` 個多群組
- 5-user：`71` 個，`1` 個多群組
- 6-user：`98` 個，`0` 個多群組
- 7-user：`78` 個，`0` 個多群組

解讀：

- 不是 UE 數多了就自然會拆群
- 就算到 6、7 個 UE，teacher 仍幾乎總是選單群組

### 2. 按 previous quality range 看

`p3_6_teacher_audit/full_bundle/by_quality_range_bucket.csv`

- `range = 0`：`587` 個，`0` 個多群組
- `range = 1`：`26` 個，`1` 個多群組
- `range = 2`：`1` 個，`0` 個多群組

解讀：

- 大部分 snapshot 的 previous quality 本來就非常一致
- quality state 雖然已經不是常數，但群內異質性仍偏低

### 3. 按 CQI range 看

`p3_6_teacher_audit/full_bundle/by_cqi_range_bucket.csv`

- `range = 0`：`269` 個，`0` 個多群組
- `range = 1`：`161` 個，`1` 個多群組
- `range = 2`：`128` 個，`0` 個多群組
- `range = 3+`：`56` 個，`0` 個多群組

解讀：

- 即使有一些 snapshot 的 CQI range 已經到 2 或 3 以上
- teacher 仍沒有因此得到明顯的拆群收益

這表示現在的 bottleneck 不只是 CQI range，而是：

- 每個 UE 的實際 resource-cost profile 還太相近
- 或 RB budget 壓力還不夠強
- 或 previous quality / switching tradeoff 還不足以改變 grouping 決策

## 那唯一一個多群組案例是什麼

`p3_6_teacher_audit/full_bundle/top_teacher_gain_scenarios.csv`

唯一被切成 2 群的 snapshot：

- `scenario_id = simu5g_00000182`
- `timestamp_s = 11.3`
- `serving_gnb = gnb_2`
- `ue_ids = 0|1|16|17|2`
- `teacher_group_count = 2`
- `teacher_group_sizes = 4|1`

但它其實不是「真正有收益」的拆群案例：

- `teacher_utility = 0.7090781116502739`
- `single_group_utility = 0.7090781116502738`
- `teacher_gain_vs_single = 1.11e-16`

這只是浮點數等級的平手，不是實際研究意義上的 improvement。

而且這個案例還有兩個很重要的訊號：

- `resource_cost_range = 0.0`
- `teacher_avg_quality` 與 `single_avg_quality` 完全相同
- `teacher_switching` 與 `single_switching` 完全相同

所以更合理的解讀是：

- 這不是 teacher 真正被逼出 split decision
- 而是 tie 情況下剛好回傳了另一個等價 partition

## 研究意義

### 1. 我們現在終於能非常有把握地說

第一輪 coupled learner 沒有分出差異，主因不是 learner 太弱，而是：

- teacher label 幾乎完全退化成 single-group policy

### 2. 當 teacher 沒有 decision diversity 時

後面的 learner 研究都會一起塌掉：

- contrastive 正負 pair 很少
- 幾乎沒有 meaningful negative supervision
- teacher-imitation 指標會虛高
- 六種方法看起來都一樣

### 3. 現在真正該優先解的問題不是模型，而是資料 regime

也就是要把 coupled trace 從：

- `single-group trivial regime`

推到：

- `teacher occasionally prefers split grouping`

只有進到後者，learner 的價值才有空間顯現。

## 下一步建議

### 收斂方向

先把這個 audit 當成 gating result：

- 如果 `positive_gain_count = 0`
- 或 `multi_group_ratio` 幾乎為 0

那就不要先擴 learner matrix。

### 下一個最應該做的資料方向

優先讓 coupled trace 裡出現更強的 grouping tradeoff：

- 更高的 cell-edge / cell-center 混合
- 更高的 per-user resource-cost dispersion
- 更長時間、更多 UE 的 overlap
- 更緊的實際 resource pressure
- 更明顯的 previous-quality heterogeneity
- 更容易出現 split 才有 QoE 優勢的 congestion segment

### 一句話總結

P3.6d 的結論非常清楚：
現在的 coupled trace 已經足以跑通 learner pipeline，但還不足以讓 offline teacher 產生真正的多群組 supervision；
因此下一步應優先增強資料中的 grouping decision pressure，而不是先擴大 learner 實驗矩陣。
