# P3.6j-2b Shape-Mismatch Variant

Last updated: 2026-08-06

## 背景

`P3.6j-2` 的第一版 cost-side redesign 有一個明確限制：

- 它直接加重了原本就被 teacher isolate 的 `ue 15`
- `resource_cost_range` 的確被拉大
- 但 `teacher_gain_vs_single` 反而從原本的高點掉下來

所以 `P3.6j-2b` 改成測試另一個方向：

> 不再只懲罰已經被 isolate 的 user  
> 而是去改一個本來屬於主群、CQI 很強的 user  
> 讓它的 per-band rate shape 變差  
> 看 teacher 的分群結構會不會因此改變

核心想法是：如果我們能讓「哪一個 user 應該被切出去」這件事變得更曖昧，teacher 才有機會出現更有辨識度的 split decision。

## 為什麼不是只換 band 順序

這一步先確認了 `le_gra_mvp.py` 的 cost 計算方式：

- `user_resource_cost_vector()` 會先把每個 user 的 `rb_rates` 由高到低排序
- `allocate_and_evaluate()` 用排序後的 rate profile 來決定 multicast cost

因此：

> 單純交換 band index 沒有效果  
> `j-2b` 必須真的改變排序後的 rate multiset  
> 才會影響 cost economics

這也是 `shape-mismatch` 這個名字的來源。

## 設計

### 目標 family

- `0|1|15|2|3|4|5 @ gnb_1`

### 目標時間窗

- `43.7s`
- `43.8s`
- `43.9s`

### 目標 user

- `ue 4`

選 `ue 4` 的原因：

- 它原本屬於 teacher 主群，不是已經被 isolate 的 `ue 15`
- 它的 `cqi_now = 15`，是很強的 CQI user
- 如果連這種 user 的 cost shape 都能被拉歪，teacher grouping 才可能真的改寫

## 實作

使用：

- `build_p3_6j2b_shape_mismatch_bundle.py`

輸出：

- `p3_6j2b_shape_mismatch_bundle/`

這個腳本會從 `p3_6i2_coupled_bundle` 複製資料，然後只修改 `ue 4` 在 `seg_01` 三個 snapshot 的 `rb_rates`：

- `rate >= 1128 kbps` 乘上 `0.72`
- `rate >= 984 kbps` 乘上 `0.82`
- 其餘 rate 乘上 `0.92`

同步更新的檔案：

- `bundle/rb_rates.csv`
- `radio/radio_rbs.csv`

這代表：

- mobility 不變
- CQI metadata 不變
- previous-quality 不變
- 改的只有 cost shape

## 正式結果

### Teacher audit

正式執行：

- `python run_p3_6_teacher_decision_audit.py --bundle-dir p3_6j2b_shape_mismatch_bundle/bundle --out-dir p3_6j2b_teacher_audit`

`full_bundle/summary.csv`：

- `scenario_count = 830`
- `multi_group_count = 9`
- `positive_gain_count = 9`
- `mean_teacher_gain_vs_single = 0.00020322910762139208`
- `max_teacher_gain_vs_single = 0.03242487072117384`

### Focus mining

正式執行：

- `python mine_focus_slices.py --audit-csv p3_6j2b_teacher_audit/full_bundle/scenario_teacher_decisions.csv --out-dir p3_6j2b_focus_mining`

`summary.txt`：

- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 7`
- `near_miss_family_count = 13`

### seg_01 結果

`seg_01` 仍然是主要觀察點：

- family: `0|1|15|2|3|4|5 @ gnb_1`
- time: `43.7s ~ 43.9s`

在 `p3_6i2` 原本的 teacher split 中，這段是：

- `[[0,1,3,4,5,6],[2]]`

到了 `j-2b`，正式 audit 顯示這段變成：

- `[[0,1,3,4,6],[2,5]]`

注意這裡的數字是 scenario 內的 user index，不是 UE ID。  
但重點很清楚：

- teacher grouping 真的被改動了
- 不只是數值變動，而是 split 結構本身換了

對應 gain：

- `p3_6i2 seg_01 gain = 0.057159402144`
- `p3_6j-2 seg_01 gain = 0.031898927110`
- `p3_6j-2b seg_01 gain = 0.032424870721`

## 解讀

`P3.6j-2b` 告訴我們一件很重要的事：

> shape mismatch 比單純 penalty 更接近我們真正想找的方向

因為它做到兩件 `j-2` 沒做到的事：

- 它真的改變了 teacher grouping structure
- 它比 `j-2` 稍微回升了一點 gain

但它也有明確限制：

- gain 還是遠低於 `p3_6i2` 原本的 `0.057159`
- 正增益 snapshot 數量沒有增加
- 正增益 segment 數量也沒有增加

所以目前最合理的判斷是：

> 單一 user 的 shape-mismatch 還不夠  
> 它能擾動 teacher 的決策邊界  
> 但還沒有把 split-vs-single 的優勢真正放大

## 對 P3.6j 的位置

到目前為止，`P3.6j` 的幾個方向可以整理成：

1. `j-1`
   - 全域 quality divergence 不夠
2. `j-1b`
   - 過強的 targeted divergence 會傷到原本的 split advantage
3. `j-1c`
   - 溫和 targeted divergence 只能保住原本 regime，無法擴大差距
4. `j-2`
   - 直接懲罰 isolate user 會拉高 cost range，但不會放大 gain
5. `j-2b`
   - 改主群高 CQI user 的 cost shape，能改變 grouping，但還不夠把 gain 拉高

## 下一步

最值得繼續做的是：

### P3.6j-2c dual-candidate mismatch

方向是：

- 不只改一個 user
- 同時製造兩個候選 user 的 mismatch
- 讓 teacher 在不同 snapshot 之間，可能對不同 user 產生 isolate 傾向

這樣比較有機會同時做到：

- 放大 `teacher - no-group`
- 讓 `multi-feature` 更難用靜態特徵學到穩定規則
- 讓 LE-GRA 的 temporal / structured 優勢更容易被看見

## 一句話結論

`P3.6j-2b` 是第一個「真的把 teacher grouping 搖動」的 cost-side redesign，但它還沒有把 teacher gain 拉回甚至超過 `p3_6i2`；下一步應該從單一 user mismatch，升級成雙候選者的 mismatch 結構。
