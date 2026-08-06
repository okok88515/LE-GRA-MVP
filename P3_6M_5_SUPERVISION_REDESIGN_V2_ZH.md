# P3.6m-5 supervision redesign v2: boundary-aware sampling + positive-gain weighting

## 目的

`P3.6m-5 v1` 已經證明：

- 單純的 `teacher_hard_group` pair weighting 不夠
- 最關鍵的問題是 supervision coverage 太稀薄
- hardest-group negative pairs 幾乎沒有真正進到訓練

所以 `P3.6m-5 v2` 的目標不是再加大權重，
而是直接補 coverage。

## v2 的兩個改動

### 1. pair-level：`teacher_boundary` sampling

在 `le_gra_mvp.py` 中新增 `teacher_boundary` pair sampling。

做法：

- positive pairs：
  - 先抽 teacher hardest group 內部、且有加權的 priority positives
  - 不足再用一般 positives 補滿
- negative pairs：
  - 先抽 hardest group 對外、且有加權的 priority negatives
  - 不足再用一般 negatives 補滿

這代表 v2 不只是「如果抽到就加權」，
而是會主動優先保留 weakest-group boundary 的 pair。

### 2. scenario-level：`positive_multigroup_focus`

在 `run_p3_6_coupled_learner.py` 中新增 scenario weighting。

做法：

- 若 teacher 是 multi-group scenario：
  - 至少重複 `multigroup_boost = 2`
- 若 teacher 相對 single-group 有正增益：
  - 至少重複 `positive_gain_boost = 4`

目的：

- 減少大量 single-group / non-informative scenarios 稀釋 supervision
- 讓真正包含 split signal 的 scenarios 在每個 epoch 裡被看得更常

## 程式修改

### `le_gra_mvp.py`

新增：

- `prioritize_pairs(...)`
- `pair_sampling = teacher_boundary`

新的 train-side diagnostics：

- `priority_positive_pairs`
- `priority_negative_pairs`

### `run_p3_6_coupled_learner.py`

新增訓練參數：

- `--scenario-weight-mode`
- `--positive-gain-boost`
- `--multigroup-boost`

並將以下欄位寫入結果：

- `scenario_weight_mode`
- `positive_gain_boost`
- `multigroup_boost`
- `train_priority_positive_pairs`
- `train_priority_negative_pairs`
- `train_schedule_examples`
- `train_boosted_scenarios`

### `run_p3_6g_temporal_learner.py`

將同一組 v2 參數接入 focused temporal learner protocol。

## 實驗設定

主評估 regime 不變：

- bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
- focus family: `0|1|15|2|3|4|5 @ gnb_1`
- train window end: `43.6s`
- test window: `43.7s ~ 43.9s`

輸出：

- `p3_6m5_teacher_boundary_v2/`

命令：

```powershell
python -u .\run_p3_6g_temporal_learner.py `
  --bundle-dir p3_6m4b_threshold_nudge_bundle\bundle `
  --out-dir p3_6m5_teacher_boundary_v2 `
  --focus-ue-ids 0 1 15 2 3 4 5 `
  --train-window-end 43.6 `
  --test-window-start 43.7 `
  --test-window-end 43.9 `
  --max-groups 3 `
  --epochs 12 `
  --feature-mode history_cost_quality `
  --pair-sampling teacher_boundary `
  --supervision-weight-mode teacher_hard_group `
  --hard-positive-scale 2.5 `
  --hard-negative-scale 1.5 `
  --scenario-weight-mode positive_multigroup_focus `
  --positive-gain-boost 4 `
  --multigroup-boost 2 `
  --seed 9
```

## 結果

### Main comparison

主結果仍然完全不變：

- `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`

主要數值：

- `Offline teacher = 0.579609048805`
- `LE-GRA MVP = 0.579083105194`
- `Multi-feature = 0.579083105194`
- `No grouping = 0.547184178084`

### Teacher-imitation diagnostics

三個 test snapshots 也仍然完全不變：

- `pairwise_accuracy = 0.714285714286`
- `ARI = 0.416666666667`
- `NMI = 0.428140178120`

也就是說：

- `LE-GRA` 仍然停在 `ue15-only` split identity
- 還是沒有學會 teacher 的 dual-weak `{ue15, ue4}`

## 與 v1 的關鍵差異

雖然最終 utility 和 partition 沒變，
但 v2 在 train-side coverage 上確實有明顯改變。

### v1

- `train_negative_pairs = 0.0444`
- `train_hard_group_negative_pairs = 0.0444`

### v2

- `train_negative_pairs = 0.1722`
- `train_hard_group_negative_pairs = 0.1722`
- `train_priority_negative_pairs = 0.1722`
- `train_schedule_examples = 697.0`
- `train_boosted_scenarios = 7.0`

也就是說：

- boundary negatives 確實有被補進來
- positive-gain / multi-group scenarios 也真的被重複訓練了

但即使如此，最終 test partition 還是沒有變。

## 最重要的新結論

`P3.6m-5 v2` 的價值在於它把 bottleneck 又往前推了一步：

- 問題不再只是「coverage 太少」
- 因為 coverage 補上後，LE-GRA 還是沒有改 partition

目前更精準的結論是：

- **現有 pairwise contrastive supervision 本身，不足以把 `{ue15, ue4}` 這種 teacher weak-group identity 穩定寫進 embedding geometry**

也就是說，現在最該懷疑的不是資料量，
而是 supervision 形式本身。

## 解讀

在目前 regime 下，teacher 的核心知識其實不是單純 pairwise same/different：

- teacher 判斷的是「哪些人應該一起被視為 weak group」
- 而不是只有「兩兩是否同群」

對 `{ue15, ue4}` 這種 secondary weak structure 而言，
pairwise loss 很可能太扁平：

- 它能鼓勵局部靠近或分離
- 但未必能把「一整個弱組身份」穩定刻進最終 k-means partition

## 建議下一步

`P3.6m-5 v3` 不應再只是微調 pair sampling 或 boost 係數。

更值得優先做的是 supervision form redesign，例如：

1. group-prototype / weak-group center supervision
   - 明確學 hardest group 作為一個 cluster identity

2. split-candidate ranking / group-membership score
   - 直接預測誰屬於 teacher weak group，而不只做 pairwise contrastive

3. regret-aware soft target
   - 不只用 teacher 最終 partition
   - 而是把 near-best partitions 或 weak-group membership uncertainty 也編進 supervision

一句話總結：

`P3.6m-5 v2` 已經證明，即使把 boundary coverage 和 positive-gain scenario weighting 都補上，LE-GRA 仍然學不會 `{ue15, ue4}`，所以下一步應該從 **pairwise supervision** 轉向 **group-identity supervision**。
