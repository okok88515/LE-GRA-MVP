# P3.6j-2f Third-Candidate Collapse

Last updated: 2026-08-06

## 目標

`j-2d / j-2e` 已經把我們帶到一個很明確的 plateau：

- `43.8s / 43.9s` 都能維持 flipped grouping
- 但 flipped snapshots 的 gain 固定卡在 `0.007690339299`

所以 `P3.6j-2f` 的任務不是再微調同一組 `ue 4 / ue 5`，而是刻意跨出這個 plateau：

> 加入第三個 cost-side candidate  
> 再疊局部 previous-quality offset  
> 看 teacher 會不會變成更豐富的分群，或直接崩回單群

## 設計

### Base

- `p3_6i2_coupled_bundle`

### Family

- `0|1|15|2|3|4|5 @ gnb_1`

### Target timestamps

- `43.8s`
- `43.9s`

### 變動訊號

1. 維持 `ue 4 / ue 5` 的 dual-candidate transform
2. 新增第三個 cost candidate：`ue 0`
3. 在 `43.8s / 43.9s` 加入局部 previous-quality offset

## 實作

使用：

- `build_p3_6j2f_third_candidate_collapse_bundle.py`

輸出：

- `p3_6j2f_third_candidate_collapse_bundle/`

### Rate transform

`ue 4`

- `>=1128 kbps` 乘上 `0.70`
- `>=984 kbps` 乘上 `0.84`
- 其餘乘上 `0.94`

`ue 5`

- `>=1128 kbps` 乘上 `0.92`
- `>=984 kbps` 乘上 `0.95`
- 其餘乘上 `0.98`

`ue 0` 作为第三候選者：

- `>=1128 kbps` 乘上 `0.94`
- `>=984 kbps` 乘上 `0.97`
- 其餘乘上 `0.99`

### Previous-quality override

在 `43.8s / 43.9s`：

- `ue 15 -> previous_quality = 2`
- `ue 4 -> previous_quality = 0`
- `ue 5 -> previous_quality = 0`

這個設計的重點是：

- 不是單純再把更多人變差
- 而是讓 `ue 15 / ue 4 / ue 5 / ue 0` 共同形成一個更混亂的 decision surface

## 正式結果

### Teacher audit

執行：

- `python run_p3_6_teacher_decision_audit.py --bundle-dir p3_6j2f_third_candidate_collapse_bundle/bundle --out-dir p3_6j2f_teacher_audit`

`summary.csv`：

- `scenario_count = 830`
- `multi_group_count = 7`
- `max_teacher_group_count = 2`
- `positive_gain_count = 7`
- `mean_teacher_gain_vs_single = 0.00015489752928427535`
- `max_teacher_gain_vs_single = 0.05715940214371462`

### Focus mining

執行：

- `python mine_focus_slices.py --audit-csv p3_6j2f_teacher_audit/full_bundle/scenario_teacher_decisions.csv --out-dir p3_6j2f_focus_mining`

`summary.txt`：

- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 5`
- `near_miss_family_count = 13`

## seg_01 的結果

### base (`p3_6i2`)

- `43.7s`: `[[0,1,3,4,5,6],[2]]`
- `43.8s`: `[[0,1,3,4,5,6],[2]]`
- `43.9s`: `[[0,1,3,4,5,6],[2]]`

### `j-2f`

- `43.7s`: `[[0,1,3,4,5,6],[2]]`
- `43.8s`: `[[0,1,2,3,4,5,6]]`
- `43.9s`: `[[0,1,2,3,4,5,6]]`

也就是說：

- `43.8s / 43.9s` 不再維持 flipped grouping
- teacher 直接回到 single-group

對應 gain：

- `43.7s gain = 0.057159402144`
- `43.8s gain = 0.0`
- `43.9s gain = 0.0`

`seg_01` 也因此從三格 segment 退化成只剩：

- `43.7s ~ 43.7s`

## 解讀

這個結果很重要，因為它告訴我們：

> 把第三個 candidate 和 quality offset 加進來，  
> 並不會自然把 teacher 推向三群或更豐富的 split，  
> 反而更容易把 split incentive 直接抹掉。

也就是說，在目前這個 family 裡：

- ambiguity 太少，會回到原本單切式二群
- ambiguity 太多，則會直接 collapse 成單群

而 `j-2d / j-2e` 那個 plateau，反而像是一條很窄但穩定的平衡帶。

## 和前幾版比較

### `j-2c`

- 一格 flip
- 平均 gain 較高

### `j-2d / j-2e`

- 兩格連續 flip
- gain 較低，但仍為正

### `j-2f`

- 企圖跨出 plateau
- 結果不是更複雜分群
- 而是 `43.8/43.9` 直接 collapse 為單群

## 關於三群以上

`j-2f` 也再次驗證：

- 目前仍然沒有 `teacher_group_count >= 3` 的案例
- 加入第三個 candidate 也沒有自然長出三群

這讓「teacher 本身偏好單切式分法」這件事更可信。

## 研究意義

`j-2f` 是目前最清楚的 plateau boundary test：

- `j-2d / j-2e` 說明 plateau 存在
- `j-2f` 說明離開 plateau 的第一個方向，不是進入 richer partition，而是 collapse

這個結論很重要，因為它告訴我們未來若要再拉大差距，方向應該不是：

- 繼續往同一 family 疊更多 candidate

而比較可能要：

- 改 family 組成
- 改更上游的 mobility / CQI structure
- 或者另找新的 informative family

## 一句話結論

`P3.6j-2f` 成功跨出了 `j-2d/j-2e` 的 plateau，但跨出去後看到的不是三群，而是 `43.8/43.9` 的 single-group collapse。
