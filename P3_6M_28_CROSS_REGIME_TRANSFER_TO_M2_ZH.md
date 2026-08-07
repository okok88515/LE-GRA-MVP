# P3.6m-28 cross-regime transfer check to `m2`

交接日期：2026-08-07

## 這一步在回答什麼

`P3.6m-26 ~ P3.6m-27` 已經證明：

- 在最困難的 `m4b` dual-weak regime 上
- `localized hard negatives + membership_order`
- 可以讓 `LE-GRA` 對齊 teacher

但那還只是一條主 regime 的成功。

第 2 階段真正要問的是：

- 這條新路徑是不是只對 `m4b` 特例有效？
- 還是它其實可以 transfer 到另一個已知 focused regime？

因此這一步選擇已經存在、而且過去曾被驗證過的 `m2` family 來做最小 cross-regime check。

## 為什麼選 `m2`

`m2` 不是新的隨機 bundle，而是目前 repo 裡另一條已知有研究脈絡的 focused regime：

- bundle：`p3_6m2_positive_family_decoy_bundle/bundle`
- focus family：`0|1|15|2|3|4|5 @ gnb_1`
- 舊結果中，`kmeans_embedding` 就已可在 focused holdout 上對齊 teacher

所以這次不是要證明「新方法讓原本失敗的 `m2` 突然成功」。

真正目標比較務實：

1. 確認 `m4b` 上有效的新 supervision/inference 組合搬到別的 regime 不會退化
2. 看 weak-group audit 是否也維持一致的 teacher-aligned behavior
3. 讓我們知道目前這條方法是「`m4b` 專用 hack」還是已經有跨 regime 穩定性

## 實驗設定

命令：

```bash
python -u run_p3_6g_temporal_learner.py \
  --bundle-dir p3_6m2_positive_family_decoy_bundle/bundle \
  --out-dir p3_6m28_m2_localized_hard_negative_membership_order \
  --focus-ue-ids 0 1 15 2 3 4 5 \
  --background-train-limit 150 \
  --train-window-end 43.7 \
  --test-window-start 43.8 \
  --test-window-end 43.9 \
  --restart-seeds 7 9 11 \
  --joint-supervision-mode m4b_localized_hard_negative_v1 \
  --grouping-mode membership_order
```

關鍵設定：

- bundle：`p3_6m2_positive_family_decoy_bundle/bundle`
- `joint_supervision_mode = m4b_localized_hard_negative_v1`
- `grouping_mode = membership_order`
- focused holdout：`43.8 ~ 43.9`
- output：`p3_6m28_m2_localized_hard_negative_membership_order/`

## 主結果

主表結果如下：

- `Offline teacher = 0.579609048805`
- `LE-GRA MVP = 0.579609048805`
- `CQI / resource-cost / multi-feature = 0.579083105194`

也就是說：

- 新方法搬到 `m2` 之後沒有退化
- `LE-GRA` 仍然可以和 teacher 完全對齊
- 而且仍然保有對 baseline 的小幅優勢

## Weak-group audit 重點

最重要的 focused holdout 兩個時間點：

- `43.8s`
- `43.9s`

在 `weak_group_prediction_audit.csv` 中都出現：

- `teacher_candidate_signature = 15|4`
- `predicted_topk_signature = 15|4`
- `teacher_candidate_hit_count = 2`
- `teacher_secondary_in_predicted_topk = 1`

這代表：

- learner 的 weak ranking 不只是最後 utility 剛好對
- 它在 holdout 上連 teacher 的 dual-weak candidate 結構都一起對上了

## 這一步最重要的意義

### 1. `m4b` 的成功不是完全孤例

如果這套方法一離開 `m4b` 就退化，我們會更傾向把它視為局部修補。

但目前 `m2` 的 cross-regime check 顯示：

- 新 supervision 不會破壞已經可解的 regime
- `membership_order` 也不是只能在 `m4b` 才成立

這讓整條方法開始有「可轉移」的味道，而不只是單點修復。

### 2. 目前最像 bottleneck 的問題更清楚了

到這一步為止，我們可以更有把握地說：

- 在困難 regime 上，局部 frontier supervision 可以修正 weak ranking
- `membership_order` 可以把修正後的 weak signal 接到最終 grouping
- 所以主問題已經不再是「learner 完全學不到」
- 而是哪些 regime 真的需要這條 bridge、哪些 regime 原本就夠容易

### 3. 第 2 階段的下一個合理方向

既然 `m2` 沒有退化，下一步不應再停留在「它也可以跑通」。

更有資訊量的問題會變成：

1. 哪些 regime 只有舊方法就夠，哪些 regime 一定要 `membership_order`
2. 哪些 regime 會出現和 `m4b` 一樣的 dual-weak frontier mismatch
3. 能不能把這些 regime 分成：
   - easy / already-solvable
   - bridge-needed
   - still-unsolved

## 小結

`P3.6m-28` 的結論很直接：

- `localized hard negatives + membership_order`
- 不只在 `m4b` 有效
- 也能穩定 transfer 到另一條已知 focused regime `m2`
- 而且 holdout 的 weak-group candidate 結構同樣和 teacher 對齊

這代表我們現在不是只有「單點 breakthrough」，
而是開始有一條可以跨 regime 使用的候選方法線。
