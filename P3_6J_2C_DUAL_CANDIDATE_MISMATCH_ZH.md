# P3.6j-2c Dual-Candidate Mismatch

Last updated: 2026-08-06

## 背景

到 `P3.6j-2b` 為止，我們已經確認兩件事：

- 單純懲罰原本就會被 isolate 的 `ue 15`，不會把 teacher gap 拉大
- 去改一個主群高 CQI user 的 cost shape，雖然可以搖動 teacher grouping，但還是不夠

所以 `P3.6j-2c` 的目標不再是只做出「另一個比較貴的人」，而是進一步做出：

> 同一個 family 裡，同時出現兩個候選 split user  
> 讓 teacher 在時間上出現一次真正的 split identity flip

也就是說，這一步更重視的是「決策邊界變得曖昧」而不是單點把 cost range 再推高。

## 設計想法

### 目標 family

- `0|1|15|2|3|4|5 @ gnb_1`

### 目標時間

- 只改 `43.8s`

這是一個刻意的選擇。  
我們沒有把整段 `43.7s ~ 43.9s` 全部改掉，而是只改中間 snapshot，原因是：

- `43.7s` 和 `43.9s` 保留原本高增益的 teacher split
- `43.8s` 變成雙候選擾動點
- 這樣可以在同一個正增益 segment 裡觀察 teacher 的 grouping 是否會翻動

### 目標 user

- `ue 4`
- `ue 5`

兩者原本都屬於主群，CQI 很強。  
因此 `j-2c` 不是在強化既有 isolate，而是在主群內部製造新的 split 候選者。

## 實作

使用：

- `build_p3_6j2c_dual_candidate_mismatch_bundle.py`

輸出：

- `p3_6j2c_dual_candidate_mismatch_bundle/`

### Rate transform

`ue 4` 採用較強的 top-end 壓縮：

- `>=1128 kbps` 乘上 `0.70`
- `>=984 kbps` 乘上 `0.84`
- 其餘乘上 `0.94`

`ue 5` 採用較輕的廣泛壓縮：

- `>=1128 kbps` 乘上 `0.92`
- `>=984 kbps` 乘上 `0.95`
- 其餘乘上 `0.98`

所以這不是兩個 user 套同一組懲罰，而是：

- 一個被做成主要候選者
- 一個被做成次要候選者

目的是讓 teacher 在 `43.8s` 看到「不只一個可切出去的人」。

## 正式結果

### Teacher audit

正式執行：

- `python run_p3_6_teacher_decision_audit.py --bundle-dir p3_6j2c_dual_candidate_mismatch_bundle/bundle --out-dir p3_6j2c_teacher_audit`

`summary.csv`：

- `scenario_count = 830`
- `multi_group_count = 9`
- `positive_gain_count = 9`
- `mean_teacher_gain_vs_single = 0.00023302974788951336`
- `max_teacher_gain_vs_single = 0.05715940214371462`

### Focus mining

正式執行：

- `python mine_focus_slices.py --audit-csv p3_6j2c_teacher_audit/full_bundle/scenario_teacher_decisions.csv --out-dir p3_6j2c_focus_mining`

`summary.txt`：

- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 7`
- `near_miss_family_count = 13`

## seg_01 的關鍵變化

`seg_01` 仍然是：

- family: `0|1|15|2|3|4|5 @ gnb_1`
- time: `43.7s ~ 43.9s`

但三個 snapshot 的 grouping 不再完全一樣。

### base (`p3_6i2`)

- `43.7s`: `[[0,1,3,4,5,6],[2]]`
- `43.8s`: `[[0,1,3,4,5,6],[2]]`
- `43.9s`: `[[0,1,3,4,5,6],[2]]`

也就是原本一直都是只 isolate 一個人：

- scenario index `2` = `ue 15`

### `j-2c`

- `43.7s`: `[[0,1,3,4,5,6],[2]]`
- `43.8s`: `[[0,1,3,4],[2,5,6]]`
- `43.9s`: `[[0,1,3,4,5,6],[2]]`

重點是 `43.8s`：

- teacher 不再只 isolate `ue 15`
- 而是把 `ue 15 + ue 4 + ue 5` 拉成一個三人群

這表示：

- `43.7s / 43.9s` 還維持原始 split identity
- `43.8s` 出現了中間翻動

這就是 `j-2c` 最重要的成果。

## Cost 結構對照

以 `43.8s` 為例，mean resource cost 從：

- base: `ue 15 = 5.333333`, `ue 4 = 3.166667`, `ue 5 = 3.166667`

變成：

- `j-2c`: `ue 15 = 5.333333`, `ue 4 = 4.333333`, `ue 5 = 3.500000`

也就是：

- `ue 15` 沒有再被額外加重
- `ue 4` 被拉成新的強候選者
- `ue 5` 被拉成次級候選者

這讓 teacher 在單一 snapshot 內看到的，不再是「一個明顯弱者 + 一群完全一樣的強者」，而是「一個弱者 + 兩個逐步變貴的主群成員」。

## Gain 解讀

`seg_01` 的平均 gain 變成：

- `p3_6i2 seg_01 mean gain = 0.057159402144`
- `p3_6j-2b seg_01 mean gain = 0.032424870721`
- `p3_6j-2c seg_01 mean gain = 0.040669714529`

這裡要分成兩層看：

### 好消息

- `j-2c` 沒有像 `j-2` 一樣直接把整段打爛
- 它保住了 `43.7s` 與 `43.9s` 的原始高 gain
- 它比 `j-2b` 的 segment 平均 gain 還高
- 它真的做出了同一 family 內的 teacher identity flip

### 限制

- 全域 `max_teacher_gain_vs_single` 沒有超過 `p3_6i2`
- `positive_gain_count` 沒有增加
- `positive_segment_count` 沒有增加
- 也就是說，它還沒有把 teacher 與 baseline 的差距實際放大

## 研究意義

`j-2c` 的價值不在於「創造了更大的數字」，而在於它第一次比較乾淨地證明：

> 我們可以在不重跑 mobility / CQI / previous-quality 的情況下  
> 只透過雙候選 cost-shape redesign  
> 讓同一個正增益 family 出現 snapshot-level 的 teacher split flip

這代表下一步可以更精準地往這個方向推：

- 把 flip 做得更強
- 讓不同 snapshot 的 split identity 差更大
- 盡量不要犧牲原本高 gain snapshot

## 下一步建議

最合理的延伸是：

### P3.6j-2d

方向可以是：

- 保留 `43.7/43.9` 的原始高 gain
- 再擴增一到兩個中間 snapshot
- 繼續用雙候選或三候選 cost mismatch
- 目標不是單純拉高 cost range，而是讓 `43.8` 類型的 split flip 變得更穩定

一句話說，`j-2c` 已經把故事從「誰最弱」推進到「teacher 在局部時間裡怎麼改變它認為該切出去的人」；這對後面想拉開 `teacher / LE-GRA / multi-feature / no-group` 的差距，是比單一 penalty 更值得延伸的方向。
