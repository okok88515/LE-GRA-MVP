# P3.6f Focused Split 結果

更新日期：2026-08-06

## 這一輪做了什麼

P3.6f 不再改資料生成，而是直接重設 learner-facing split。

我們先從 `p3_6e3_teacher_audit/full_bundle/scenario_teacher_decisions.csv` 找出所有真正有正 gain 的 teacher cases，
結果非常集中：

- 正 gain snapshots：`24`
- 全部都來自同一個 UE 組合：`0|1|2|3`

因此 P3.6f 改成 focused split：

- `test_ue_ids = 0|1|2|3`
- `train_ue_ids = 15|31|4|5|6|7`

## Focused teacher audit

輸出：

- `p3_6f_teacher_audit/`

關鍵結果：

- `scenario_count = 411`
- `multi_group_count = 24`
- `multi_group_ratio = 0.05839`
- `positive_gain_count = 24`
- `positive_gain_ratio = 0.05839`
- `max_teacher_gain_vs_single = 0.03861`

這表示：

- focused split 成功把所有真正有價值的 teacher split cases 收進 learner-facing test slice
- 我們終於不再是「測一個完全沒有 split supervision 的 test set」

## Focused learner 結果

輸出：

- `p3_6f_coupled_learner/`

主結果：

- `No grouping`: utility `0.7104`
- `CQI k-means`: utility `0.7116`
- `Resource-cost k-means`: utility `0.7127`
- `Multi-feature k-means`: utility `0.7127`
- `Offline teacher`: utility `0.7127`
- `LE-GRA MVP`: utility `0.7117`

## 這一輪最重要的研究結論

### 1. Focused split 成功了

P3.6f 最重要的成果不是 learner 贏，而是：

- 我們終於把 learner-facing evaluation slice 對準了真正有 split gain 的案例

這一步非常關鍵，因為它證明之前 learner test split 看不到差異，
不是因為 coupled trace 永遠沒有研究價值，而是因為 split protocol 把有效案例切掉了。

### 2. 在這個 focused split 上，最佳 baseline 是 multi-feature / resource-cost

`Resource-cost k-means`
與 `Multi-feature k-means`
已經和 `Offline teacher` 打平。

這表示：

- 在目前這個 focused slice 上，hand-crafted resource-cost feature 已經非常強
- LE-GRA 還沒有把這些可分案例完全學起來

### 3. LE-GRA 有接近，但還沒追上 teacher

teacher-imitation diagnostics：

- `Multi-feature k-means`: pairwise / ARI / NMI 全部 `1.0`
- `LE-GRA MVP`: pairwise `0.9878`、ARI `0.9757`、NMI `0.9757`

群數分布：

- teacher：`24` 個 2-group，`387` 個 1-group
- multi-feature：完全一致
- LE-GRA：只抓到 `14` 個 2-group

所以 LE-GRA 的主要問題不是亂切，而是：

- 對一部分該 split 的 snapshots，還是保守地留在單群組

### 4. 現在 learner 的瓶頸非常清楚

train split 用的是：

- `15|31|4|5|6|7`

但真正有正 gain 的 cases 全都集中在：

- `0|1|2|3`

所以 learner 目前是在：

- 沒有看過正 gain split 類型的 UE 組合
- 然後要泛化到最關鍵的 `0|1|2|3` focused slice

這也是為什麼這一輪訓練統計仍然很弱：

- `train_negative_pairs = 0.0`

也就是說，模型在 train 端幾乎沒有得到真正的「應該分開」監督。

## 一句話總結

P3.6f 成功把 learner-facing test slice 對準了真正有研究價值的 split cases；
但結果也很清楚地說明，現在最強的不是 LE-GRA，而是 hand-crafted resource-cost / multi-feature grouping。
下一步若要讓 learner 追上，關鍵不是再擴大矩陣，而是讓 train split 也看到正 gain split supervision。
