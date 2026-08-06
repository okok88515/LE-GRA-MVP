# P3.6j-1b Seg_01 Targeted Window Divergence

Last updated: 2026-08-06

## 目標

P3.6j-1 的負結果已經很清楚：

- 全域 `previous_quality` 分歧確實被放大
- 但 teacher summary 幾乎完全沒變

因此 P3.6j-1b 的目的不是再拉大整體平均，而是更精準地問：

> 如果只在 `seg_01` 的關鍵 positive-gain 窗口
> `43.7s ~ 43.9s`
> 內，強制維持 high-group 與 low-group 的品質分歧，
> teacher gain 會不會被放大？

## 設計

P3.6j-1b 沿用 `p3_6i2` 的 raw trace 與 `rb_budget_ratio = 0.28`，
只新增一個更精準的 `previous_quality_mode`：

- `deterministic_controller_seg01_targeted`

新增檔案：

- `build_p3_6j1b_coupled_bundle.py`

## 定點干預規則

在 `simu5g_raw_radio_export.py` 的 quality-state controller 中，
對 `43.7s ~ 43.9s` 這段時間施加 family-targeted override：

### 高品質群

- `0`
- `1`
- `15`

規則：

- 進入目標時間窗時，`previous_quality` 至少維持在 `3`

### 低品質群

- `2`
- `3`
- `4`
- `5`

規則：

- 進入目標時間窗時，`previous_quality` 被壓到 `0`

這樣的目的是把 `seg_01` family 直接打成一個極化狀態：

- 高品質群：`3`
- 低品質群：`0`

不再只是 `2` 對 `1` 的輕微差異。

## 實際結果

### 1. 定點品質分歧成功生效

在 `p3_6j1b_coupled_bundle/radio/quality_state.csv` 中，
`43.7s ~ 43.9s` 的 `seg_01` 相關 UE 變成：

- `0`: `3`
- `1`: `3`
- `15`: `3`
- `2`: `0`
- `3`: `0`
- `4`: `0`
- `5`: `0`

這代表 P3.6j-1b 不是失敗在 controller 沒打進去，
而是真正成功把 targeted divergence 鎖進 `seg_01` 的關鍵窗口。

### 2. seg_01 的 previous-quality range 明顯變大

在 `p3_6j1b_teacher_audit/full_bundle/scenario_teacher_decisions.csv` 中：

- `seg_01`: `previous_quality_range = 3`
- `previous_quality_mean = 1.2857`

相比先前版本：

- `p3_6i2`: `previous_quality_range = 0`
- `p3_6j1`: `previous_quality_range = 1`
- `p3_6j1b`: `previous_quality_range = 3`

所以從 targeted-state 的角度看，P3.6j-1b 是成功的。

### 3. 但 teacher gain 反而下降

這是 P3.6j-1b 最重要的結果。

`seg_01` 的 gain 變化：

- `p3_6i2`: `0.057159`
- `p3_6j1`: `0.057159`
- `p3_6j1b`: `0.028588`

也就是說：

> 我們成功把 `seg_01` 的 previous-quality divergence 拉大，
> 但 teacher gain 沒有被放大，反而幾乎減半。

### 4. 全域 summary 也隨之下降

`full_bundle summary.csv`：

- `positive_gain_count = 9`，沒有變
- `multi_group_count = 9`，沒有變
- `max_teacher_gain_vs_single` 從 `0.057159` 降到 `0.028588`
- `mean_teacher_gain_vs_single` 也下降

`focus mining` 結果：

- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 7`
- `near_miss_family_count = 13`

數量沒有變，但 `seg_01` 的強度下降。

## 研究解讀

P3.6j-1b 的結果非常有價值，因為它排除了另一種常見但錯誤的直覺：

> 不是把 previous-quality 分歧拉得越大，
> teacher 與 baseline 的差距就會自動越大。

目前更合理的解讀是：

### 1. teacher 喜歡的是「可被 split 利用的差異」，不是任意極化

當高組被鎖在 `3`、低組被壓到 `0` 時，
這個 divergence 雖然明顯，但不一定和當下的 resource-cost / CQI 結構形成更有利的 split tradeoff。

換句話說，P3.6j-1b 製造的是：

- 很強的 state divergence

但 teacher 真正需要的可能是：

- state divergence 與 resource pressure、CQI ambiguity、group composition 同時對齊

### 2. 過度極化可能讓 single-group 也變得比較容易處理

如果高低組差異被做得太死，
teacher 的 split 空間不一定更大，反而可能讓某種 single-group compromise
變得沒有那麼差。

這可以解釋為什麼 `seg_01` 的 gain 從 `0.057` 掉到 `0.0286`。

### 3. 真正需要的是「結構化且適中的 divergence」

P3.6j-1b 告訴我們：

- `p3_6i2`：差異太弱，不一定能拉開方法差距
- `p3_6j1b`：差異太硬，反而削弱原本的 teacher gain

所以下一步應該找的是中間區：

> 不是零分歧，也不是硬鎖成 3 對 0，
> 而是能和 family 的 channel / cost 結構協同作用的適中 divergence。

## 下一步建議

P3.6j-1b 之後，最合理的方向不是繼續把 quality state 拉得更極端，
而是進一個更精細的 `P3.6j-1c / P3.6j-2`：

1. 做「溫和但持續」的 family-targeted divergence
   - 例如高組維持 `2`
   - 低組維持 `1`
   - 或只讓被 teacher isolate 的那個 user 偏離
2. 不只改 state，還要與 `resource_cost_range` / `ambiguous pair` 同步設計
3. 優先關注：
   - 哪種 divergence 會讓 `teacher - no-group` gap 增大
   - 但不會把原本的 split-gain family 弄弱

## 目前最精準的結論

P3.6j-1b 已經回答了一個很重要的研究問題：

> family/time-window targeted divergence 確實可以改變關鍵 slice 的 state structure；
> 但差異不是越大越好。若 divergence 與當下 channel/resource 結構不協調，
> teacher gain 反而會下降。

這讓下一步方向變得更清楚：

> 後續要追的不是「更大 divergence」，
> 而是「更匹配 split economics 的 divergence」。
