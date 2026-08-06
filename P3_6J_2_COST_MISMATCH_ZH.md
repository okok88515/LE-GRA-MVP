# P3.6j-2 Cost-Mismatch Variant

Last updated: 2026-08-06

## 目標

在 `P3.6j-1 / j-1b / j-1c` 之後，研究方向已經很清楚：

- 單靠 `previous_quality` manipulation，不足以穩定放大 teacher gap

所以 `P3.6j-2` 轉向另一條路：

> 保留 mobility、CQI、previous quality 不變，
> 只改關鍵 family 內某個 UE 的 per-band achievable-rate profile，
> 讓它在 wideband 看起來沒變，但實際 resource cost 更差。

這正是我們想測的 `cost mismatch`：

- 表面上 CQI 不變
- 真正的 RB 代價變大

## 設計

P3.6j-2 不是重跑 coupled simulation，而是從：

- `p3_6i2_coupled_bundle/`

複製一份新 bundle，再做後處理：

- `p3_6j2_cost_mismatch_bundle/`

使用腳本：

- `build_p3_6j2_cost_mismatch_bundle.py`

## Targeted intervention

目標 family：

- `0|1|15|2|3|4|5 @ gnb_1`

目標時間窗：

- `43.7s`
- `43.8s`
- `43.9s`

目標 UE：

- `15`

也就是目前 `seg_01` 中被 teacher isolate 的 cross-traffic user。

## Rate-profile 變形方式

對 `ue 15` 在目標時間窗的 `rb_rates` 做分段縮放：

- RB `0~7`: `0.62`
- RB `8~15`: `0.76`
- RB `16~24`: `0.88`

目的不是亂降平均，而是讓它的可用 logical-band profile 更差，
也就是讓它的 resource-cost 向量被刻意拉開。

重要的是，這一版：

- 不改 `wideband_cqi`
- 不改 `previous_quality`
- 不改 mobility / serving-gNB / trajectory

所以這是一個乾淨的 cost-side intervention。

## 執行結果

### Bundle 後處理成功

`build_p3_6j2_cost_mismatch_bundle.py` 結果：

- target scenarios: `3`
- modified bundle RB rows: `75`
- modified radio RB rows: `75`

表示 `seg_01` 三個 snapshots、`ue 15` 的全部 25 個 RB rows 都被正確改動。

## Teacher audit 結果

### seg_01 的 cost range 被明顯拉大

在 `p3_6j2_teacher_audit/full_bundle/scenario_teacher_decisions.csv` 中，
`seg_01` 變成：

- `resource_cost_range = 4.0`
- `previous_quality_range = 0`
- `teacher_gain_vs_single = 0.031899`

相比原始 `p3_6i2`：

- `resource_cost_range = 2.1667 ~ 2.3333`
- `teacher_gain_vs_single = 0.057159`

也就是說：

- cost mismatch 的確被成功放大
- 但 teacher gain 沒有變大，反而下降

### seg_02 基本不變

`0|1|2|3|4 @ gnb_2`：

- `resource_cost_range = 1.0`
- `teacher_gain_vs_single = 0.011901`

和原本一樣，表示 intervention 沒外溢到別的 family。

## 與前幾版比較

### 全域 summary

- `p3_6i2`: `max_teacher_gain_vs_single = 0.057159`
- `p3_6j1`: `0.057159`
- `p3_6j1b`: `0.028588`
- `p3_6j1c`: `0.057159`
- `p3_6j2`: `0.031899`

`positive_gain_count`、`positive_segment_count`、`candidate_temporal_slice_count`
都沒有變，仍然是：

- `positive_gain_count = 9`
- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 7`

## 研究解讀

P3.6j-2 的結果很有啟發性，因為它補上了另一條重要反例：

> 單純把被 teacher isolate 的 user 做得更貴，
> 也不會自動放大 teacher gain。

### 1. cost range 變大，不代表 split economics 更有利

直覺上會以為：

- isolate user 更貴
- 那 split 應該更有利

但這個實驗顯示，事情沒有那麼簡單。

更合理的解釋是：

- teacher 已經本來就 isolate 了 `ue 15`
- 進一步把它做得更差，只是讓整體可達 QoE 空間一起縮水
- 並沒有讓「split 相對於 single-group」的優勢變得更大

### 2. 這和 j-1b 的結論互相呼應

`j-1b` 告訴我們：

- 把 state divergence 做太極端，teacher gain 會下降

`j-2` 告訴我們：

- 把 isolated user 的 cost mismatch 做太強，teacher gain 也會下降

這兩個結果很一致地指出：

> 問題不在於差異不夠大，
> 而在於差異是否真的改善了 split 與 single-group 之間的相對 tradeoff。

### 3. 下一步不應該只「加強 isolate user 的差」

如果只是一直讓某個 user 更差：

- quality-side：會像 `j-1b` 一樣傷到原本 gain
- cost-side：會像 `j-2` 一樣讓 gain 掉下來

所以更合理的下一步應該是：

- 創造 `排序錯位`
- 而不是單純把 isolated user 做成更差

換句話說，要做的是：

> 讓 wideband 看起來接近，
> 但最佳 split 對象在不同 snapshots 會因為 per-band cost shape 而改變。

## 下一步建議

最推薦的後續不再是 `j-2a = more penalty` 這種加強版，
而應該進一個更接近真正研究目標的變體：

### P3.6j-2b：shape-mismatch instead of pure penalty

做法：

1. 不只降 `ue 15` 的整體 rate
2. 改成讓：
   - 某些高 band 很差
   - 某些中低 band 還行
3. 甚至讓兩個候選 user 在不同 band 區間各自吃虧

這樣才能更像真正的「CQI 相近但 cost profile 不同」，
而不是單純把某個 user 變成 universally worse。

## 一句話總結

P3.6j-2 的結論是：

> cost mismatch 這條路是對的，但「把 isolated user 直接做得更貴」這種純 penalty 版本不夠好；
> 它會放大 cost range，卻不會放大 teacher gain。
