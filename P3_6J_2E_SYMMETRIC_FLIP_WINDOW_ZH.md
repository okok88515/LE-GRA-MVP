# P3.6j-2e Symmetric Flip Window

Last updated: 2026-08-06

## 目標

`P3.6j-2d` 之後，我們想回答一個更精準的問題：

> 兩格連續 flip window 的 gain，能不能靠局部微調再往上抬？

所以 `P3.6j-2e` 不是亂試一個新設計，而是先做了小型離散搜尋，專門找：

- `43.7s` 保持 base 高 gain
- `43.8s` 與 `43.9s` 都保持 flipped grouping
- 並且希望把 flipped snapshots 的 gain 拉高

## 搜尋結果：出現 plateau

搜尋結果很乾淨：

- 只要 `43.8/43.9` 都維持 flipped
- 而且 `43.7` 保持 base grouping

那麼 flipped snapshots 的 gain 會穩定卡在同一個值：

- `0.007690339299`

這表示目前不是「某一組參數剛好好運」，而是：

> teacher 在這個 dual-candidate regime 下，似乎已經進入一個穩定的 utility plateau

## 因此 j-2e 的策略

既然 plateau 已經被看見，`j-2e` 就不再追求更複雜的非對稱調參，而是改做：

> 最簡單、最可解釋、最容易重現的 plateau 版本

也就是把 `j-2c` 原本成功的 dual-candidate transform，直接對稱地套到：

- `43.8s`
- `43.9s`

## 實作

使用：

- `build_p3_6j2e_symmetric_flip_window_bundle.py`

輸出：

- `p3_6j2e_symmetric_flip_window_bundle/`

### Transform

`ue 4`

- `>=1128 kbps` 乘上 `0.70`
- `>=984 kbps` 乘上 `0.84`
- 其餘乘上 `0.94`

`ue 5`

- `>=1128 kbps` 乘上 `0.92`
- `>=984 kbps` 乘上 `0.95`
- 其餘乘上 `0.98`

而且這組 transform 同時用在：

- `43.8s`
- `43.9s`

## 正式結果

### Teacher audit

執行：

- `python run_p3_6_teacher_decision_audit.py --bundle-dir p3_6j2e_symmetric_flip_window_bundle/bundle --out-dir p3_6j2e_teacher_audit`

`summary.csv`：

- `scenario_count = 830`
- `multi_group_count = 9`
- `max_teacher_group_count = 2`
- `positive_gain_count = 9`
- `mean_teacher_gain_vs_single = 0.0001734284673532704`
- `max_teacher_gain_vs_single = 0.05715940214371462`

### Focus mining

執行：

- `python mine_focus_slices.py --audit-csv p3_6j2e_teacher_audit/full_bundle/scenario_teacher_decisions.csv --out-dir p3_6j2e_focus_mining`

`summary.txt`：

- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 7`
- `near_miss_family_count = 13`

## seg_01 結果

### `j-2e`

- `43.7s`: `[[0,1,3,4,5,6],[2]]`
- `43.8s`: `[[0,1,3,4],[2,5,6]]`
- `43.9s`: `[[0,1,3,4],[2,5,6]]`

對應 gain：

- `43.7s gain = 0.057159402144`
- `43.8s gain = 0.007690339299`
- `43.9s gain = 0.007690339299`

`seg_01 mean gain = 0.024180026914`

## 和 j-2d 的關係

`j-2e` 的正式結果和 `j-2d` 完全一致：

- 相同的 `summary.csv`
- 相同的 `seg_01` 三格 grouping
- 相同的 per-snapshot gain
- 相同的 `seg_01 mean gain`

這代表一件很重要的事：

> `j-2d` 的結果不是某組不對稱參數偶然造成的  
> `j-2e` 證明只要落在同一個 dual-candidate flip regime，  
> teacher 會收斂到同樣的 plateau

## 研究意義

`j-2e` 的價值，不在於超越 `j-2d`，而在於把 `j-2d` 的現象「驗證成穩定結論」：

1. 兩格連續 flip window 是可重現的
2. 這個 regime 的 teacher gain 有明顯 plateau
3. 在目前這個 family 下，單靠這類 cost-side 微調，似乎很難把 flipped snapshots 再往上抬

## 對後續方向的影響

這意味著如果我們還想繼續拉大差距，就不該再把時間花在同一類微調上。

比較值得往下走的是：

### 路線 A

拿 `j-2c` 去跑 learner。

原因：

- `j-2c` gain 比 `j-2d/j-2e` 高
- 又已經有真正的 split identity flip

### 路線 B

如果還要繼續 scenario redesign，就要跨出目前 plateau，不能只改同一種 cost-shape 強度。

例如：

- 再引入第三個弱候選者
- 在 flipped snapshots 局部加入 previous-quality offset
- 或改 family 組成本身，而不是只改 `ue 4/5`

## 一句話結論

`P3.6j-2e` 沒有比 `j-2d` 更強，但它證明了 `j-2d` 不是巧合，而是一個可重現的 symmetric flip-window plateau。
