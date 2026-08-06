# P3.6h-2 RB=0.28 Family Follow-up

更新日期：2026-08-06

## 這一步做了什麼

在 P3.6h 確認 `rb_budget_ratio = 0.28` 會冒出新的 positive split family 之後，
這一步繼續往前做兩件事：

1. 把 `rb_028` 的 teacher audit 正式挖成 focused temporal slice 候選。
2. 直接對新 family 補跑 learner slice，確認哪一組值得成為下一輪主要研究對象。

新增通用 mining 腳本：

- `mine_focus_slices.py`

輸出：

- `p3_6h_pressure_sweep/rb_028_focus_mining/`

## rb_028 的 positive segments

在 `rb_028` 下共有 3 段 positive segments：

1. `0|1|2|3 @ gnb_2`
   - `16.2s ~ 16.4s`
   - 共 `3` 個 positive snapshots

2. `1|2|3|4|5|6 @ gnb_2`
   - `27.3s ~ 27.6s`
   - 共 `4` 個 positive snapshots

3. `3|31|4|5|6 @ gnb_2`
   - `31.1s ~ 31.2s`
   - 共 `2` 個 positive snapshots

## 可用的 temporal slice 候選

`candidate_temporal_slices.csv` 顯示共有 `6` 個候選，其中最重要的是：

### A. 最完整的新 family

- UE: `1|2|3|4|5|6`
- gNB: `gnb_2`
- segment: `27.3s ~ 27.6s`
- 最平衡切法：`split = 27.4s`
- `focus_train_positive_gain_count = 2`
- `focus_test_positive_gain_count = 2`

這是目前最值得優先擴大的新 family，因為它不只是真 split，而且 train/test 兩端都還有正增益 supervision。

### B. 較弱的新 family

- UE: `3|31|4|5|6`
- gNB: `gnb_2`
- segment: `31.1s ~ 31.2s`
- 唯一可切法：`split = 31.1s`
- `focus_train_positive_gain_count = 1`
- `focus_test_positive_gain_count = 1`

這個 family 雖然也是真 split，但訊號太短，暫時比較像 verification case，不像主要 study case。

## Learner result: `1|2|3|4|5|6 @ rb_028`

已跑：

- bundle: `p3_6h_pressure_sweep/rb_028/coupled_bundle/bundle`
- output: `p3_6h_pressure_sweep/rb_028_segA_temporal_learner/`
- focus UE: `1 2 3 4 5 6`
- `train_window_end = 27.4`
- `test_window = 27.5s ~ 27.6s`

### 結果

- `No grouping`: utility `0.5472`
- `CQI k-means`: utility `0.5708`
- `Resource-cost k-means`: utility `0.5708`
- `Multi-feature k-means`: utility `0.5708`
- `Offline teacher`: utility `0.5714`
- `LE-GRA MVP`: utility `0.5708`

### 解讀

這組 family 已經證明：

- LE-GRA 有抓到「這裡需要分兩群」
- 但它和 multi-feature / resource-cost 仍然只到 baseline 水準
- teacher 還保有一點點額外優勢

也就是說，這是一組比 `0|1|2|3` 更難的 family。

在 `0|1|2|3` 上，LE-GRA 可以完全追平 teacher；
但在 `1|2|3|4|5|6` 上，它目前只能追到強 baseline，還沒完全追到 teacher。

## Learner result: `3|31|4|5|6 @ rb_028`

已跑：

- output: `p3_6h_pressure_sweep/rb_028_segB_temporal_learner/`
- focus UE: `3 31 4 5 6`
- `train_window_end = 31.1`
- `test_window = 31.2s ~ 31.2s`

### 結果

- `No grouping`: utility `0.5672`
- `CQI k-means`: utility `0.5791`
- `Resource-cost k-means`: utility `0.5791`
- `Multi-feature k-means`: utility `0.5791`
- `Offline teacher`: utility `0.5791`
- `LE-GRA MVP`: utility `0.5672`

### 解讀

這組訊號太短，而且 test 只有 `1` 個 snapshot。

目前可得到的唯一合理結論是：

- teacher 的確在這個 family 上短暫偏向 split
- hand-crafted baseline 可以命中
- LE-GRA 在這個極短 slice 上沒有學到

但因為樣本只有 1 個 test snapshot，這組不適合作為正式研究結論，只適合當作「弱訊號 family」的提醒。

## 這輪的真正收斂

P3.6h-2 讓後續優先順序更清楚了：

### 1. `1|2|3|4|5|6 @ rb_028` 是目前最值得放大的第二個 family

原因是：

- 它是真的 positive family
- 它比 `0|1|2|3` 更難
- LE-GRA 尚未完全追平 teacher
- 它比 `3|31|4|5|6` 有更完整的 temporal window

### 2. `3|31|4|5|6 @ rb_028` 暫時不適合當主軸

原因是：

- 正增益區間只有 `2` 個 snapshots
- test slice 只能切出 `1` 個 snapshot
- 太容易被單點偶然性影響

### 3. 下一步不應該只是再多跑更多 seeds

目前最需要的不是更多重複，而是讓 `1|2|3|4|5|6` 這類 6-UE positive family 的正增益區間變長。

只要這段再長一點，我們就可以：

- 做更像樣的 temporal train/test split
- 觀察 LE-GRA 是不是會開始真正追近 teacher
- 分辨現在的差距是 supervision 長度不夠，還是 partition 表示能力不夠

## 建議下一步

最合理的下一步是：

1. 以 `1|2|3|4|5|6 @ gnb_2` 為模板做 targeted scenario redesign。
2. 目標不是製造更多 family，而是先把這個 family 的 positive window 從 `27.3~27.6s` 拉長。
3. 拉長後再重跑 focused temporal learner，確認 LE-GRA 是否能從 baseline-level 進一步追上 teacher。

