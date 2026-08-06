# P3.6m-5 supervision redesign v1: teacher hard-group pair weighting

## 目的

`P3.6m-3 / P3.6m-4` 已經把 bottleneck 收斂得很清楚：

- `LE-GRA` 不是不會 split
- 它是不會把 secondary weak candidate `ue4` 拉進弱組
- 也就是還學不會 teacher 的 dual-weak identity：`{ue15, ue4}`

所以 `P3.6m-5` 第一版不改 learner 主架構，只改 supervision。

## 核心想法

第一版 supervision redesign 採用：

- `teacher_hard_group` pair weighting

做法是先用 teacher partition 找出每個 scenario 中最難的 group
（以 mean resource cost 排序），然後在 contrastive loss 中：

- 放大 hardest group 內部的 positive pairs
- 放大 hardest group 對外的 negative pairs

目的不是讓模型只學「要 split」，
而是讓模型更重視 teacher 認為最難、最值得被獨立辨識的那個弱組。

## 程式修改

### `le_gra_mvp.py`

新增：

- `teacher_group_difficulty_order(...)`
- `pairwise_supervision_weights(...)`

並讓 `MLPEncoder.train_step(...)` 支援：

- `pair_weights`

loss 與 gradient 現在都會乘上 pair weight。

### `run_p3_6_coupled_learner.py`

新增訓練參數：

- `--supervision-weight-mode`
- `--hard-positive-scale`
- `--hard-negative-scale`

並將這些設定寫進：

- `main_comparison.csv`
- `split_summary.json`

同時額外紀錄訓練期 pair statistics：

- `train_mean_positive_weight`
- `train_mean_negative_weight`
- `train_hard_group_positive_pairs`
- `train_hard_group_negative_pairs`

### `run_p3_6g_temporal_learner.py`

把同一組 supervision 參數接進 focused temporal learner protocol，
以便直接沿用 `P3.6m-4b` 主 regime。

## 實驗設定

主評估 regime：

- bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
- focus family: `0|1|15|2|3|4|5 @ gnb_1`
- train window end: `43.6s`
- test window: `43.7s ~ 43.9s`

輸出：

- `p3_6m5_teacher_hard_group_v1/`

命令：

```powershell
python -u .\run_p3_6g_temporal_learner.py `
  --bundle-dir p3_6m4b_threshold_nudge_bundle\bundle `
  --out-dir p3_6m5_teacher_hard_group_v1 `
  --focus-ue-ids 0 1 15 2 3 4 5 `
  --train-window-end 43.6 `
  --test-window-start 43.7 `
  --test-window-end 43.9 `
  --max-groups 3 `
  --epochs 12 `
  --feature-mode history_cost_quality `
  --pair-sampling random_balanced `
  --supervision-weight-mode teacher_hard_group `
  --hard-positive-scale 2.5 `
  --hard-negative-scale 1.5 `
  --seed 9
```

## 結果

### Main comparison

結果仍然是：

- `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`

主要數值：

- `Offline teacher = 0.579609048805`
- `LE-GRA MVP = 0.579083105194`
- `Multi-feature = 0.579083105194`
- `No grouping = 0.547184178084`

也就是說：

- 第一版 weighted supervision **沒有** 讓 LE-GRA 超過 `multi-feature`
- 也沒有縮小目前的 utility gap

### Teacher-imitation diagnostics

三個 test snapshots 仍全部相同：

- `pairwise_accuracy = 0.714285714286`
- `ARI = 0.416666666667`
- `NMI = 0.428140178120`

代表：

- LE-GRA 仍然停在原本那個 `ue15-only` 的 split identity
- 還沒有學到 `{ue15, ue4}`

## 最重要的新 evidence

這次最有價值的不只是「v1 沒成功」，
而是我們終於看到 supervision 訊號本身的結構問題。

來自 `main_comparison.csv` 的 train-side pair stats：

- `train_positive_pairs = 6.2219`
- `train_negative_pairs = 0.0444`
- `train_mean_positive_weight = 2.4845`
- `train_mean_negative_weight = 1.5`
- `train_hard_group_positive_pairs = 6.1464`
- `train_hard_group_negative_pairs = 0.0444`

這代表：

- hardest-group positive supervision 幾乎每個 scenario 都有被吃到
- 但 hardest-group negative supervision 幾乎沒有

換句話說，第一版 redesign 雖然放大了弱組內聚，
但沒有真的提供足夠多的「把 decoy weak user 跟強組拉開」的訓練訊號。

## 解讀

`P3.6m-5 v1` 的結論不是「supervision redesign 沒必要」，
而是：

- 單純用 teacher hardest-group pair weighting 還不夠
- 當前資料切分下，真正關鍵的跨組 negative signal 太稀薄

因此目前更精準的 bottleneck 變成：

- learner 不只缺 supervision 強度
- learner 缺的是 **能穩定覆蓋 secondary weak boundary 的 supervision coverage**

## 建議下一步

`P3.6m-5 v2` 應優先朝這兩種方向做，而不是先擴大實驗：

1. 做 group-boundary-aware pair construction
   - 明確保證 hardest group 對外的 negatives 被抽到
   - 特別是 secondary weak candidate 與強組成員之間

2. 做 positive-gain / dual-weak scenario weighting
   - 提高真正含有 `{ue15, ue4}` teacher structure 的 scenario 訓練權重
   - 避免大量單弱者或單群 scenario 稀釋 supervision

一句話總結：

`P3.6m-5 v1` 已經證明「只加 hardest-group weighting 不足以教會 LE-GRA secondary weak identity」，下一版應該把重點從 `weighting` 進一步推到 `pair coverage`。
