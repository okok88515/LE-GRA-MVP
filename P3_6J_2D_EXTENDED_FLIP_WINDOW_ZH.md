# P3.6j-2d Extended Flip Window

Last updated: 2026-08-06

## 目標

`P3.6j-2c` 已經證明一件事：

- 在 `seg_01` 裡，我們可以只靠 cost-side redesign
- 讓 teacher 在單一 snapshot (`43.8s`) 出現 split identity flip

但 `j-2c` 的 flip 只有一格，時間上還太短。  
所以 `P3.6j-2d` 的目標是：

> 把原本只有一個 snapshot 的 dual-candidate ambiguity  
> 擴成一個比較長的 flip window  
> 同時盡量保住正 gain

## 另外一個明確問題：有沒有三群以上？

在開始 `j-2d` 前，我們先做了兩層檢查：

1. 掃描目前所有正式 teacher audit
2. 對 `seg_01` 做額外的離散局部搜尋

目前結果一致：

- 所有正式 audit 的 `max_teacher_group_count` 都是 `2`
- 沒有任何已知 snapshot 出現 `teacher_group_count >= 3`
- 在 `seg_01` 的額外 144 組局部 probe 中，也沒有找到三群案例

所以到 2026-08-06 為止，這個專案裡還沒有實際觀察到 teacher 分成三群以上的例子。

## 設計

### Base

- `p3_6i2_coupled_bundle`

### Family

- `0|1|15|2|3|4|5 @ gnb_1`

### Target timestamps

- `43.8s`
- `43.9s`

### Target users

- `ue 4`
- `ue 5`

## 核心想法

`j-2d` 不是把 `j-2c` 原封不動複製到整段，而是把雙候選壓力拆成兩層：

- `43.8s`：保留 `j-2c` 那種比較強的 flip 設計
- `43.9s`：換成另一組較溫和但仍有辨識度的 shape mismatch

這樣做的目的是：

- `43.7s` 保留原始高 gain
- `43.8s ~ 43.9s` 形成連續 ambiguity window
- 不要因為壓太重而讓整段 collapse

## 實作

使用：

- `build_p3_6j2d_extended_flip_window_bundle.py`

輸出：

- `p3_6j2d_extended_flip_window_bundle/`

### 43.8s

`ue 4`

- `>=1128 kbps` 乘上 `0.70`
- `>=984 kbps` 乘上 `0.84`
- 其餘乘上 `0.94`

`ue 5`

- `>=1128 kbps` 乘上 `0.92`
- `>=984 kbps` 乘上 `0.95`
- 其餘乘上 `0.98`

### 43.9s

`ue 4`

- `>=1128 kbps` 乘上 `0.88`
- `>=984 kbps` 乘上 `0.68`
- 其餘乘上 `0.90`

`ue 5`

- `>=1128 kbps` 乘上 `0.84`
- `>=984 kbps` 乘上 `0.90`
- 其餘乘上 `0.96`

## 正式結果

### Teacher audit

執行：

- `python run_p3_6_teacher_decision_audit.py --bundle-dir p3_6j2d_extended_flip_window_bundle/bundle --out-dir p3_6j2d_teacher_audit`

`summary.csv`：

- `scenario_count = 830`
- `multi_group_count = 9`
- `max_teacher_group_count = 2`
- `positive_gain_count = 9`
- `mean_teacher_gain_vs_single = 0.0001734284673532704`
- `max_teacher_gain_vs_single = 0.05715940214371462`

### Focus mining

執行：

- `python mine_focus_slices.py --audit-csv p3_6j2d_teacher_audit/full_bundle/scenario_teacher_decisions.csv --out-dir p3_6j2d_focus_mining`

`summary.txt`：

- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 7`
- `near_miss_family_count = 13`

## seg_01 的關鍵變化

### base (`p3_6i2`)

- `43.7s`: `[[0,1,3,4,5,6],[2]]`
- `43.8s`: `[[0,1,3,4,5,6],[2]]`
- `43.9s`: `[[0,1,3,4,5,6],[2]]`

### `j-2d`

- `43.7s`: `[[0,1,3,4,5,6],[2]]`
- `43.8s`: `[[0,1,3,4],[2,5,6]]`
- `43.9s`: `[[0,1,3,4],[2,5,6]]`

也就是說：

- 原本只有一格 flipped snapshot
- 現在變成 `43.8s ~ 43.9s` 兩格連續 flipped snapshots

這就是 `j-2d` 最重要的成果。

## Gain 變化

`seg_01`：

- `43.7s gain = 0.057159402144`
- `43.8s gain = 0.007690339299`
- `43.9s gain = 0.007690339299`

`seg_01 mean gain = 0.024180026914`

和前幾版比較：

- `p3_6i2 seg_01 mean gain = 0.057159402144`
- `p3_6j-2b seg_01 mean gain = 0.032424870721`
- `p3_6j-2c seg_01 mean gain = 0.040669714529`
- `p3_6j-2d seg_01 mean gain = 0.024180026914`

## 解讀

`j-2d` 的效果很鮮明：

### 成功的地方

- 它真的把 flip 從單一 snapshot 拉成兩個連續 snapshots
- 它沒有把這段變成負 gain，兩格 flipped snapshots 還是正值
- 它讓 `seg_01` 的 temporal ambiguity 更強、更穩定

### 代價

- 平均 gain 明顯下降
- 它比 `j-2c` 更擅長製造 temporal flip
- 但比 `j-2c` 更不擅長維持高 teacher advantage

換句話說：

> `j-2d` 更像是「把 teacher 決策邊界拉長」  
> 而不是「把 teacher 與 baseline 的 utility gap 拉大」

## 對研究脈絡的意義

到這一步，我們已經有兩個不同型態的 cost-side regime：

### `j-2c`

- 單一 flipped snapshot
- 平均 gain 較高
- temporal ambiguity 較短

### `j-2d`

- 兩個連續 flipped snapshots
- 平均 gain 較低
- temporal ambiguity 較長

這是一個很有價值的分叉，因為它把問題拆成兩個可研究方向：

1. 想拉大 utility gap
2. 想拉長 temporal ambiguity window

目前看起來，這兩個目標不一定會一起變好。

## 關於三群以上的暫時結論

目前可以先寫成一個暫時研究結論：

> 在現有 `seg_01` family、現有 offline teacher、以及目前這批 cost-side redesign 裡，  
> teacher 非常傾向維持單切式或雙群式分法，  
> 還沒有證據顯示它自然會走到三群以上。

這可能代表：

- 現在的 utility 結構偏好「切一刀」而不是多段切分
- 或者目前的 scenario ambiguity 還不夠多層次

## 下一步建議

如果下一步目標是拉大 `teacher / LE-GRA / multi-feature / no-group` 的差距，建議分成兩條：

### 路線 A：拿 `j-2c` 去做 learner

因為：

- 它保留較高 gain
- 又已經有真正的 snapshot-level flip

比較可能兼顧：

- teacher gap
- learner imitation難度

### 路線 B：在 `j-2d` 上做 `j-2e`

方向是：

- 保留兩格連續 flip
- 只微調其中一個 flipped snapshot 的強度
- 試著把 `0.00769` 再抬高

一句話總結：`j-2d` 已經成功把單點 flip 做成短窗 flip，但它也證明了 temporal ambiguity window 變長，未必會讓 teacher gain 一起變大。
