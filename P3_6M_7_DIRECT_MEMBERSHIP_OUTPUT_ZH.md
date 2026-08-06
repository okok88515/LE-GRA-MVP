# P3.6m-7 direct weak-group membership output

## 目的

`P3.6m-6` 已經把問題壓到一個很明確的位置：

- weakest-group identity signal 已經進到訓練
- 但只要最後還是走 `embedding + k-means`
- `LE-GRA` 就仍然無法把 teacher 的 dual-weak identity `{ue15, ue4}` 轉成正確 split

因此 `P3.6m-7` 的目標是做真正的 output-form change：

- 不再把 `LE-GRA` 的最終輸出綁死在 k-means
- 讓 learner 直接輸出 weakest-group membership scores
- 再用這些 scores 來產生 candidate split

## 核心改動

### 1. 新增 weak-group membership head

在 `MLPEncoder` 上新增一個最小 head：

- `w4`, `b4`
- 對第二層 hidden state 輸出每個 UE 的 weakest-group membership score

新增方法：

- `weak_group_scores(...)`

並在訓練中加入 membership BCE supervision：

- `membership_weight`

target 仍來自 teacher hardest group membership。

### 2. `LE-GRA` grouping 不再強制經過 k-means

新增：

- `best_membership_groups(...)`

做法：

- 用 predicted weak-group scores 對 UE 排序
- 直接沿著這個 order 做 contiguous boundary search
- 用相同 DP evaluator 選 utility 最好的 grouping

也就是說，這版的 `LE-GRA` 不再是：

- `embedding -> k-means -> DP`

而是：

- `membership score -> ordered split search -> DP`

這是 `P3.6m` 目前第一個真正離開 k-means output layer 的 learner 版本。

## 實驗設定

主 regime 保持不變：

- bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
- focus family: `0|1|15|2|3|4|5 @ gnb_1`
- train window end: `43.6s`
- test window: `43.7s ~ 43.9s`

輸出：

- `p3_6m7_membership_head_v1/`

命令：

```powershell
python -u .\run_p3_6g_temporal_learner.py `
  --bundle-dir p3_6m4b_threshold_nudge_bundle\bundle `
  --out-dir p3_6m7_membership_head_v1 `
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
  --membership-weight 1.0 `
  --grouping-mode membership_order `
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

三個 test snapshots 仍然完全相同：

- `pairwise_accuracy = 0.714285714286`
- `ARI = 0.416666666667`
- `NMI = 0.428140178120`

也就是說：

- 即使 `LE-GRA` 的輸出形式已經從 k-means 改成 direct membership order
- 它仍然沒有學會 `{ue15, ue4}`

## Train-side evidence

這版不是沒有弱組訊號：

- `membership_weight = 1.0`
- `train_membership_terms = 3.7791`
- `train_mean_weak_score = 0.9707`

也保留了前一版的 coverage / identity signal：

- `train_negative_pairs = 0.1722`
- `train_priority_negative_pairs = 0.1722`
- `train_prototype_positive_terms = 3.6069`
- `train_prototype_negative_terms = 0.0373`

所以 `P3.6m-7` 的關鍵意義是：

- 現在不是「head 沒加」
- 也不是「output 還被 k-means 限制」
- 而是即便改成 direct membership output，最後仍然沒動

## 最重要結論

`P3.6m-7` 是目前最強的一個 learner-side negative result。

它說明：

- 問題已經不只在 supervision
- 也不只在 clustering head
- 而是當前 learner 還沒有從目前資料與 target form 中學出可泛化的
  secondary weak candidate rule

更直白地說：

- **目前這個資料切法與 learner family 下，`LE-GRA` 仍然沒有足夠證據學會把 `ue4` 視為應進弱組的使用者**

## 解讀

這代表下一步不應該只是：

- 再調 loss 權重
- 再調 head 係數
- 或再換一個很像的 output trick

更值得做的是：

1. richer supervision target
   - 例如 soft teacher partition / near-best partition family

2. more explicit regime-focused labels
   - 專門對 dual-weak positive slices 建 harder supervision

3. training-set redesign
   - 不是增加矩陣規模，而是提高真正含 secondary-weak structure 的 train evidence density

一句話總結：

`P3.6m-7` 已經證明，即使把 learner output 改成 direct weak-group membership order，LE-GRA 仍然無法超過 `multi-feature`；下一步應該從「改 head」轉向「改 supervision target 與 train evidence design」。
