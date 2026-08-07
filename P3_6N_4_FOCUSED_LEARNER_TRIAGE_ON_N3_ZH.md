# P3.6n-4 focused learner triage on `n3`

交接日期：2026-08-07

## 目的

`P3.6n-3` 已經成功把：

- `3|4|5|6 @ gnb_2`

從 near-miss 改造成新的 teacher-positive focused regime。

下一步最重要的問題不是再改 scenario，
而是先做 learner triage，確認這條新 regime 在 learner 端屬於哪一類：

1. easy
2. bridge-needed
3. genuinely unsolved

## 使用的 focused split

根據：

- `p3_6n3_focus_mining/candidate_temporal_slices.csv`

最平衡的切法是：

- segment: `25.8s ~ 29.9s`
- suggested split: `27.8s`
- `focus_train_positive_gain_count = 21`
- `focus_test_positive_gain_count = 21`

所以這次使用：

- `train end = 27.8`
- `test = 27.9 ~ 29.9`

focus UE：

- `3 4 5 6`

## 實驗

### Run A: old baseline path

輸出：

- `p3_6n3a_baseline_kmeans/`

命令核心：

```bash
python -u run_p3_6g_temporal_learner.py \
  --bundle-dir p3_6n3_isolate_ue5_bundle/bundle \
  --out-dir p3_6n3a_baseline_kmeans \
  --focus-ue-ids 3 4 5 6 \
  --background-train-limit 150 \
  --train-window-end 27.8 \
  --test-window-start 27.9 \
  --test-window-end 29.9 \
  --restart-seeds 7 9 11
```

設定重點：

- `joint_supervision_mode = none`
- `grouping_mode = kmeans_embedding`

### Run B: membership-order bridge check

輸出：

- `p3_6n3b_baseline_membership_order/`

命令核心：

```bash
python -u run_p3_6g_temporal_learner.py \
  --bundle-dir p3_6n3_isolate_ue5_bundle/bundle \
  --out-dir p3_6n3b_baseline_membership_order \
  --focus-ue-ids 3 4 5 6 \
  --background-train-limit 150 \
  --train-window-end 27.8 \
  --test-window-start 27.9 \
  --test-window-end 29.9 \
  --restart-seeds 7 9 11 \
  --grouping-mode membership_order
```

設定重點：

- `joint_supervision_mode = none`
- `grouping_mode = membership_order`

## 結果

兩個 run 的主結果完全一致：

- `No grouping = 0.380936391692`
- `CQI k-means = 0.456624985427`
- `Resource-cost k-means = 0.460388133563`
- `Multi-feature k-means = 0.460388133563`
- `Offline teacher = 0.460388133563`
- `LE-GRA MVP = 0.460388133563`

也就是說：

- 舊 `kmeans_embedding` 已經可以完全對齊 teacher
- 換成 `membership_order` 也沒有再提升

## support-side 訊號

這次 focused learner 的 support-selection 也很乾淨：

- `support_selection_pairwise_accuracy = 1.0`
- `support_selection_ari = 1.0`
- `support_selection_nmi = 1.0`
- `support_selection_utility_gap = 0.0`

代表：

- 在這條新 regime 上
- learner 並沒有明顯的 support mismatch

## 最重要的結論

### 1. `n3` 是新的 teacher-positive regime，但不是新的 learner hard regime

這一步很重要，因為它把兩件事分開了：

- 生成新的正向 regime source：成功
- 生成新的 learner 難題：目前沒有成功

`n3` 的價值在於它證明我們能主動造出新的正向 regime，
但 learner 端看起來它屬於：

- easy / already-solvable

### 2. `n3` 不是 bridge-needed

因為如果它是 bridge-needed，我們通常會看到：

- `kmeans_embedding` 卡住
- `membership_order` 才對齊

但這次不是。

這次是：

- `kmeans_embedding = teacher`
- `membership_order = teacher`

所以它不屬於 `m4b` 那種 inference-mismatch 型 hard regime。

### 3. 新 source 的成功標準需要再往前推

目前 `n3` 更像是：

- 把一個 near-miss family 推成 clean positive regime
- 但推成的形式是很乾淨的「單弱者隔離」

這種 regime 對 teacher 很有意義，
但對 learner 不一定夠難。

如果我們的目標是再拉大：

- teacher
- LE-GRA
- multi-feature
- no-group

之間的差距，那下一步要找的就不是任意 positive regime，
而是：

- teacher 明顯 split
- 但 learner 不會立刻跟上

換句話說，要更接近：

- positive
- but not trivially linearly separable
- and ideally not already solved by old `kmeans_embedding`

## 對整體研究的意義

目前我們已經有三種很清楚的 regime 類型：

1. `m2`
   - easy / already-solvable

2. `m4b`
   - bridge-needed

3. `n3`
   - newly generated positive regime
   - but still easy

這很有幫助，因為它告訴我們：

- regime generation 已經不是問題
- 但要生成「對 learner 真正困難」的新 regime，還需要更進一步

## 下一步建議

最合理的下一步不是直接在 `n3` 上做更多 learner tweak，
因為它已經被解掉了。

更有資訊量的方向是：

1. 以 `n3` 為 base，再往更高難度設計：
   - 不只是單弱者 isolation
   - 而是雙弱者 / ambiguous weak ordering
   - 或讓最終 grouping 不再是明顯的 one-vs-rest

2. 具體來說，優先嘗試：
   - 讓 `ue5` 與另一個 UE 同時接近弱者邊界
   - 讓 teacher split 不再是穩定單點隔離，而變成 candidate ambiguity
   - 看能不能把 `n3` 從 easy 推成新的 bridge-needed regime

## 小結

`P3.6n-4` 的結論很乾淨：

- `n3` 成功成為新的 teacher-positive focused regime
- 但 learner 用舊路徑就已經能完全對齊 teacher

所以：

- `n3` 是新的 positive source
- 不是新的 hard learner source

接下來要追的，不是把 `n3` 再做更多同類 learner 實驗，
而是把 `n3` 再設計成更 ambiguous、更接近 `m4b` 類型的新 regime。
