# P3.6m-5 supervision redesign v3: hardest-group prototype supervision

## 目的

`P3.6m-5 v1` 與 `v2` 已經把問題壓得很清楚：

- `v1` 證明單純加權還不夠
- `v2` 證明即使把 boundary coverage 和 positive-gain scenario weighting 都補上，最終 partition 仍然不變

所以 `v3` 的目的，是再往前走一步：

- 不再只做 pairwise supervision
- 直接加入 weak-group identity supervision

## 核心想法

`v3` 保留 `v2` 的：

- `teacher_boundary` pair sampling
- `positive_multigroup_focus` scenario weighting
- `teacher_hard_group` pair weighting

但另外新增 hardest-group prototype supervision。

做法：

- 先從 teacher partition 中找出 hardest group
- 將 hardest group 內成員的 embedding 拉向同一個 prototype center
- 對 hardest group 外的成員，若它們離該 prototype 太近，則施加 margin-based repulsion

這代表 supervision 的語意已經從：

- 「兩兩是否同群」

往前推成：

- 「哪一群才是 teacher 認定的 hardest weak group」

## 程式修改

### `le_gra_mvp.py`

新增：

- `hardest_group_membership(...)`

並讓 `MLPEncoder.train_step(...)` 支援：

- `hard_group_target`
- `prototype_weight`
- `prototype_margin`

這個 prototype 項是加在現有 contrastive loss 上的額外 group-identity signal。

### `run_p3_6_coupled_learner.py`

新增訓練參數：

- `--prototype-weight`
- `--prototype-margin`

並寫入結果欄位：

- `prototype_weight`
- `prototype_margin`
- `train_prototype_positive_terms`
- `train_prototype_negative_terms`

### `run_p3_6g_temporal_learner.py`

將相同參數接進 focused temporal learner protocol。

## 實驗設定

主 regime 仍保持不變：

- bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
- focus family: `0|1|15|2|3|4|5 @ gnb_1`
- train window end: `43.6s`
- test window: `43.7s ~ 43.9s`

輸出：

- `p3_6m5_group_identity_v3/`

命令：

```powershell
python -u .\run_p3_6g_temporal_learner.py `
  --bundle-dir p3_6m4b_threshold_nudge_bundle\bundle `
  --out-dir p3_6m5_group_identity_v3 `
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
  --prototype-weight 0.5 `
  --prototype-margin 1.0 `
  --seed 9
```

## 結果

### Main comparison

結果仍然完全不變：

- `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`

主要數值：

- `Offline teacher = 0.579609048805`
- `LE-GRA MVP = 0.579083105194`
- `Multi-feature = 0.579083105194`
- `No grouping = 0.547184178084`

### Teacher-imitation diagnostics

三個 test snapshots 仍然完全相同：

- `pairwise_accuracy = 0.714285714286`
- `ARI = 0.416666666667`
- `NMI = 0.428140178120`

也就是說：

- prototype supervision 仍然沒有讓 `LE-GRA` 學會 `{ue15, ue4}`
- 最終 partition 還是停在 `ue15-only`

## Train-side evidence

這次不是「prototype 根本沒吃到」。

從 `main_comparison.csv` 可看到：

- `train_prototype_positive_terms = 3.6069`
- `train_prototype_negative_terms = 0.0488`
- `prototype_weight = 0.5`

同時 `v2` 的 coverage 改善仍然保留：

- `train_negative_pairs = 0.1722`
- `train_priority_negative_pairs = 0.1722`
- `train_schedule_examples = 697.0`
- `train_boosted_scenarios = 7.0`

所以 `v3` 的關鍵意義是：

- weakest-group identity signal 確實被加進訓練了
- 但最終 grouping 還是完全沒動

## 最重要的新結論

`P3.6m-5 v3` 讓我們可以把 bottleneck 收斂到目前最精準的位置：

- 問題不只是 pair sampling
- 問題不只是 scenario weighting
- 問題甚至不只是缺少弱組 identity signal

而是：

- **當前的 embedding + k-means 這個輸出形式，本身就不足以穩定表達 teacher 的 dual-weak weak-group identity `{ue15, ue4}`**

## 解讀

在現在這個 regime 下，teacher 的決策其實比較像：

- 「辨識一個弱組身份」

而不是：

- 「把所有 pairwise 關係都調到對」

就算我們把 hardest-group identity 當成 prototype 來教，
最後仍然要經過：

- embedding geometry
- k-means 初始化 / 分割
- 再由 DP 選群

這個流程可能已經把 teacher 的弱組語意壓扁了。

## 建議下一步

`P3.6m-5` 到 `v3` 為止，已經足夠支持一個新的研究判斷：

- 不要再繼續在「pairwise / prototype supervision 小修」上投入太多時間

更值得的下一步是直接進入新的 learner form，例如：

1. weak-group membership head
   - 直接預測 hardest-group membership
   - 再由 membership 導出候選 split

2. direct split-structure learner
   - 直接預測誰應該被放進 secondary weak group

3. soft teacher / near-best partition learner
   - 不只學單一 teacher partition
   - 把 `{ue15, ue4}` 附近的 partition uncertainty 也納入 supervision

一句話總結：

`P3.6m-5 v3` 已經證明，即使把 weak-group identity 直接做成 prototype supervision，LE-GRA 仍然無法超過 `multi-feature`，因此下一步應該從「調 supervision」轉向「改 learner output form」。
