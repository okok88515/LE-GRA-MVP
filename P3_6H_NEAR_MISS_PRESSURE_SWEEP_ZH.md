# P3.6h Near-miss Pressure Sweep

更新日期：2026-08-06

## 這一步在回答什麼

P3.6g 之後，我們已經知道：

- 目前 coupled trace 中真正有正增益 split 的 family 很少
- 這不一定代表 LE-GRA 的應用場景很罕見
- 更可能代表目前資料中的多數 snapshot 還沒有進入足夠強的 split regime

因此 P3.6h 的目的不是先改 learner，而是先問一個更基本的問題：

> 如果我們只沿用同一份 raw trace，單純再加大資源壓力，原本的 near-miss family 會不會被推成真正的 positive-gain split family？

這一步能幫我們分辨：

- 問題主要是不是因為 RB 壓力還不夠
- 還是必須同時再強化通道差異與 quality-state 異質性

## 實作

新增腳本：

- `run_p3_6h_near_miss_pressure_sweep.py`

輸出目錄：

- `p3_6h_pressure_sweep/`

做法是直接重用 `p3_6e_coupled_output/` 同一份 raw trace，並用異質 quality controller 重建多個 bundle：

- `rb_budget_ratio = 0.32`
- `rb_budget_ratio = 0.28`
- `rb_budget_ratio = 0.24`
- `rb_budget_ratio = 0.20`

每個 ratio 都會重新：

1. build coupled bundle
2. 跑 full-bundle teacher decision audit
3. 彙整正增益 split family 與 near-miss family 變化

## Sweep 結果總覽

`pressure_sweep_summary.csv`：

- `0.32`：`24` 個 positive snapshots，`1` 個 positive family
- `0.28`：`9` 個 positive snapshots，`3` 個 positive family
- `0.24`：`3` 個 positive snapshots，`2` 個 positive family
- `0.20`：`0` 個 positive snapshots，`0` 個 positive family

最重要的觀察是：

**split 不是隨著壓力增加而單調變多，而是出現一個 sweet spot。**

也就是：

- 壓力太鬆時，single-group 就夠好，不需要 split
- 壓力適中偏緊時，split 開始有價值
- 壓力再過度緊縮時，整體品質層被迫一起下降，split 反而失去操作空間

## 新出現的 positive families

在 `rb_budget_ratio = 0.28`，出現了兩個相對於 `0.32` 全新的正增益 split family：

1. `1|2|3|4|5|6 @ gnb_2`
   - `positive_snapshot_count = 4`
   - 時間：`27.3s ~ 27.6s`
   - `max_teacher_gain_vs_single = 0.0530`
   - `max_cqi_range = 6`
   - `max_resource_cost_range = 1.1667`

2. `3|31|4|5|6 @ gnb_2`
   - `positive_snapshot_count = 2`
   - 時間：`31.1s ~ 31.2s`
   - `max_teacher_gain_vs_single = 0.0119`
   - `max_cqi_range = 5`
   - `max_resource_cost_range = 0.8333`

原本的正增益 family `0|1|2|3 @ gnb_2` 在 `0.28` 仍存在，但縮小成：

- `positive_snapshot_count = 3`
- 時間：`16.2s ~ 16.4s`

到了 `0.24`：

- `1|2|3|4|5|6 @ gnb_2` 只剩 `1` 個 positive snapshot
- `1|2|3|4|5 @ gnb_2` 新出現 `2` 個 positive snapshots

到了 `0.20`：

- 全部 positive family 消失

## near-miss family progression

P3.6g 原本鎖定的 top near-miss families 進展如下：

### `1|2|3|4|5|6 @ gnb_2`

- `rb_032`：`0/18` positive
- `rb_028`：`4/18` positive
- `rb_024`：`1/18` positive
- `rb_020`：`0/18` positive

這是 P3.6h 最強的訊號：這個 family 不是不存在 split 潛力，而是真的被 RB 壓力推進了 split regime。

### `3|31|4|5|6 @ gnb_2`

- `rb_032`：`0/16` positive
- `rb_028`：`2/16` positive
- `rb_024`：`0/16` positive
- `rb_020`：`0/16` positive

這代表它也存在 narrow sweet spot，但比 `1|2|3|4|5|6` 更脆弱。

### `2|3|4|5|6 @ gnb_2`

- 各個 ratio 都沒有變成 positive family

### `0|1|2|3|4|5 @ gnb_2`

- `rb_032` 與 `rb_028` 都沒有 positive snapshot
- 到 `rb_024` 仍然沒有正增益

這代表不是所有 high-dispersion near-miss family 都會因為單純加壓而轉成 split。

## 研究意義

P3.6h 幫我們把前面的判斷再往前收斂了一步。

### 1. teacher 很少 split，不只是因為「使用者差異太小」

這次 sweep 顯示，只改 RB 壓力就能讓部分 near-miss family 變成 positive family。

因此比較準確的說法是：

- 問題不是單純「用戶間品質差異太小」
- 而是 **通道差異、resource-cost dispersion 與資源壓力要同時落在正確區間**

### 2. split regime 有 sweet spot，不是越壓越好

這一點非常重要，因為它直接影響後續 scenario redesign 方向。

如果我們只用「更小的 RB budget」當作唯一手段，可能會把情境推到另一個極端：

- 所有人都一起被壓低品質
- split 雖然理論上還能切，但實際上 utility gain 不再明顯

所以後面設計 informative coupled trace 時，應該追求的是：

- 適中但確實存在的 pressure
- 配上夠大的同-cell 異質性

而不是一味把 budget 往下砍。

### 3. 我們現在終於有第二個可用 split family 候選

`1|2|3|4|5|6 @ rb_028` 已經不是 near-miss，而是實際正增益 split family。

這代表 P3.6g 不再只綁在 `0|1|2|3` 那一組上，研究可以開始檢查：

- LE-GRA 能不能在第二個 family 上也學到 split
- 如果可以，它和 multi-feature 的差距到底還剩多少

## 直接往前做的一步：rb_028 family learner slice

我已經直接用新 family 跑了一個 focused temporal learner：

- bundle：`p3_6h_pressure_sweep/rb_028/coupled_bundle/bundle`
- focus UE：`1|2|3|4|5|6`
- `train_window_end = 27.4`
- `test_window = 27.5s ~ 27.6s`

輸出目錄：

- `p3_6h_pressure_sweep/rb_028_segA_temporal_learner/`

### Split summary

- `background_train_scenarios = 500`
- `focus_train_scenarios = 173`
- `focus_test_scenarios = 2`
- `focus_train_positive_gain_count = 13`
- `focus_test_positive_gain_count = 2`

### Main comparison

- `No grouping`: utility `0.5472`
- `CQI k-means`: utility `0.5708`
- `Resource-cost k-means`: utility `0.5708`
- `Multi-feature k-means`: utility `0.5708`
- `Offline teacher`: utility `0.5714`
- `LE-GRA MVP`: utility `0.5708`

### 判讀

這組結果和 `0|1|2|3` family 不完全一樣：

- LE-GRA 已經學到「要切成兩群」
- 但它和 multi-feature / resource-cost 一樣，只追到 `0.5708`
- 還沒有完全追上 teacher 的 `0.5714`

teacher-imitation diagnostics 顯示：

- Multi-feature k-means 與 LE-GRA 的表現相同
- `pairwise_accuracy = 0.6667`
- `ARI = 0.3478`
- `NMI = 0.4099`

這代表：

- 新 family 已經可以當成第二組 learner-facing split supervision
- 但它比 `0|1|2|3` family 更難，因為「分兩群」本身不夠，還要分對 partition

## 現在最合理的結論

P3.6h 讓研究脈絡更完整了：

1. split family 很少，不是因為 LE-GRA 毫無用處，而是 informative regime 本來就稀少。
2. 只要壓力調到對的 sweet spot，確實可以把 near-miss family 推成真 split family。
3. 但不是所有 family 都會因為「更小 RB budget」自然變好，表示未來 scenario redesign 還是要同步強化異質性結構。
4. `1|2|3|4|5|6 @ rb_028` 已經成為第二個可用 learner slice，且難度高於 `0|1|2|3`。

## 建議下一步

最自然的下一步有兩條：

1. 把 `rb_028` 的新 positive families 再切出更多 temporal slices，確認 learner 結果不是 2-snapshot 偶然。
2. 以 `1|2|3|4|5|6 @ gnb_2` 為模板做 scenario redesign，嘗試把這類 6-UE family 的正增益區間拉長，讓 learner 測試集不只剩 2 個 snapshot。

如果要往研究品質更高的方向走，我會優先做第 2 條，因為目前這組新 family 已經夠有啟發，但 test 規模仍然太小。

