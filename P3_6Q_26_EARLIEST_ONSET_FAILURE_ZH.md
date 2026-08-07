# P3.6q-26 最早 crossover onset failure 驗證

## 背景

`P3.6q-24 ~ q-25` 已經把新 regime 的核心瓶頸收斂到同一個點：

- family: `3|4|5|6 @ gnb_2`
- late positive corridor: `28.3s ~ 28.8s`
- teacher split: `3|5 / 4|6`
- plain LE-GRA:
  - `28.4s ~ 28.8s` 可以追上 teacher
  - 但 `28.3s` 這個最早 onset 還是會退回 single-group

所以 `q-26` 的目標很單純：

- 直接檢查 `28.3s` 到底是
  - 少了 onset 前夕的 temporal support
  - 還是即使補了 learner-side localized supervision，仍然無法及時切換

## 實驗設計

### A. pre-onset plain transfer

artifact:

- `p3_6q26_pre_onset_plain/`

command:

```bash
python run_p3_6g_temporal_learner.py \
  --bundle-dir p3_6q23_dual_boundary_crossover_bundle/bundle \
  --out-dir p3_6q26_pre_onset_plain \
  --focus-ue-ids 3 4 5 6 \
  --background-train-limit 150 \
  --train-window-end 28.2 \
  --test-window-start 28.3 \
  --test-window-end 28.3 \
  --test-include-timestamps 28.3 \
  --max-groups 3 \
  --epochs 12 \
  --restart-seeds 7 9 11 \
  --grouping-mode kmeans_embedding
```

結果：

- `Offline teacher = 0.5790955890522329`
- `LE-GRA MVP = 0.5721841780840183`
- predicted grouping:
  - teacher = `3|5 / 4|6`
  - LE-GRA = `3|4|5|6`

### B. pre-onset replay check

artifact:

- `p3_6q26_pre_onset_replay/`

command:

```bash
python run_p3_6g_temporal_learner.py \
  --bundle-dir p3_6q23_dual_boundary_crossover_bundle/bundle \
  --out-dir p3_6q26_pre_onset_replay \
  --focus-ue-ids 3 4 5 6 \
  --background-train-limit 150 \
  --train-window-end 28.2 \
  --test-window-start 28.3 \
  --test-window-end 28.3 \
  --test-include-timestamps 28.3 \
  --max-groups 3 \
  --epochs 12 \
  --restart-seeds 7 9 11 \
  --grouping-mode kmeans_embedding \
  --boundary-support-start 27.9 \
  --boundary-support-repeat 16 \
  --boundary-support-positive-only
```

最重要結果：

- `boundary_support_selected_scenarios = 0`
- `effective_boundary_support_scenarios = 0`
- `LE-GRA MVP` 完全不變，仍是 `0.5721841780840183`

這個結果非常重要，因為它證明：

- `27.9s ~ 28.2s` 這段雖然已經很接近 onset
- 但 teacher 還沒有認為那裡存在正增益 split
- 所以 replay 路徑在這個 regime 上先天沒有可重放的正增益樣本

換句話說：

- `28.3s` 不是「正增益 split 的延續」
- 它就是這個 regime 的第一個真正 split onset

### C. learner-side minimal localized supervision

artifact:

- `p3_6q26_pre_onset_joint/`

核心設定：

- `pair_sampling = teacher_boundary`
- `supervision_weight_mode = teacher_candidate_boundary`
- `candidate_membership_weight = 4.0`
- `candidate_secondary_scale = 4.0`

結果：

- `Offline teacher = 0.5790955890522329`
- `LE-GRA MVP = 0.5721841780840183`

弱群預測：

- train side `27.9s ~ 28.2s`
  - teacher candidate = `4|5`
  - predicted top-k = `3|4`
- test side `28.3s`
  - teacher candidate = `4|6`
  - predicted top-k = `5|4`
  - `ue6` rank = `4`

解讀：

- candidate-conditioned localized supervision 沒有把 secondary weak role 從 `ue5` 提前轉成 `ue6`
- 甚至在 onset 點上，`ue6` 仍然沒有進入前二

### D. stronger frontier hard-negative check

artifact:

- `p3_6q26_pre_onset_hard_negative/`

額外設定：

- `frontier_contrast_weight = 6.0`
- `frontier_negative_top_k = 2`
- `frontier_margin = 0.25`

結果：

- `Offline teacher = 0.5790955890522329`
- `LE-GRA MVP = 0.5721841780840183`

弱群預測：

- `28.3s`
  - teacher candidate = `4|6`
  - predicted top-k = `4|5`
  - `ue6` rank = `3`

解讀：

- 加上 frontier hard negatives 後，`ue6` 的排序只有些微回升
- 但仍然沒有跨過關鍵門檻，無法把最終 grouping 推向 split

## 核心結論

`q-26` 把目前 bottleneck 說得更清楚了：

1. `28.3s` 是這個 regime 的第一個真正 split onset
2. onset 之前沒有正增益 split，因此 replay 在這裡先天缺少素材
3. 只靠 learner-side localized weighting / candidate BCE / frontier hard negatives，仍然無法把 `ue6` 提前拉進正確候選集合

所以目前最合理的判斷是：

- 這不是一般的 final grouping closure 問題
- 也不是單純 boundary replay 不夠
- 而是「secondary weak-role switch 的最早 onset 表徵」仍然不足

## 下一步方向

如果要繼續放大差距，最值得做的不是再微調同一組權重，而是往以下兩條方向前進：

1. onset-aware structure
   - 讓 learner 明確看到「上一個弱候選是誰、現在誰正在接手」
   - 例如加入 weak-candidate temporal delta / ranking-change features

2. stronger dataset-side onset shaping
   - 設計讓 `ue5 -> ue6` 的交接更乾淨、更持續一點
   - 讓最早 onset 不只出現一個點，而是形成 `2~4` 個連續 snapshot 的薄 corridor

目前不值得再做的事：

- replay-only repeat sweep
- 單純 candidate weight 微調
- 再加一輪相同 frontier margin 小修
