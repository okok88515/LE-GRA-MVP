# P3.6m-2 positive-family decoy injection

## 目的

`P3.6m` 已經證明：

- `1|2|4|5 @ gnb_2` 可以做出 dual-candidate split 結構
- 但沒有正增益
- `0|1|15|2|3|4|5 @ gnb_1` 則有真實正增益 split
- 但原本比較像單弱者 isolation family

所以 `P3.6m-2` 的目標是把這兩條方向合在一起：

- 從本來就有正增益 split 的 family 出發
- 注入第二個 plausible weak decoy
- 觀察能不能在不打掉 gain basin 的前提下，提高 ambiguity

## 新增 builder

- `build_p3_6m2_positive_family_decoy_bundle.py`

輸出：

- `p3_6m2_positive_family_decoy_bundle/`
- `p3_6m2_teacher_audit/`
- `p3_6m2_family_focus/`
- `p3_6m2_focus_mining/`

## 設計

目標 family：

- `0|1|15|2|3|4|5 @ gnb_1`

關鍵時間窗：

- `43.4s ~ 43.9s`

base bundle 原始狀態：

- `43.4s ~ 43.6s` 還是 single-group
- `43.7s ~ 43.9s` teacher 會做正增益 split
- 原始 split：
  - `[[0,1,3,4,5,6],[2]]`
  - 被隔離的是 local index `2 = ue 15`
  - `teacher_gain_vs_single = 0.057159402144`

`P3.6m-2` 的策略是：

- 保留 `ue 15` 作為真正的 primary weak user
- 把 `ue 4` 注入成較輕的 decoy
- decoy 以 history 為主、cost 為輔，避免直接把原本 gain basin 打掉

具體改動：

### `ue 4` decoy

- `rb_rates` / `radio_rbs`
  - 只有非常小的 rate penalty
  - `>=1128 kbps -> 0.985`
  - `>=984 kbps -> 0.980`
  - `else -> 0.990`
- history 改成 recent decline
  - `cqi_t_minus_4 = current + 0.9`
  - `cqi_t_minus_3 = current + 0.6`
  - `cqi_t_minus_2 = current + 0.1`
  - `cqi_t_minus_1 = current - 1.0`

### `ue 15` primary weak reinforcement

- 不再額外加重 resource penalty
- 只把 history 再整理成更明顯的 recent decline

## 結果

### 1. 正增益 split 被保住了

在 `p3_6m2_teacher_audit/full_bundle/scenario_teacher_decisions.csv` 中，
目標 family 的結果是：

- `43.4s ~ 43.6s`
  - 仍為 single-group
- `43.7s ~ 43.9s`
  - 仍為正增益 multi-group

新的 segment：

- `p3_6m2_focus_mining/positive_segments.csv`
- `seg_01 = 0|1|15|2|3|4|5 @ gnb_1`
- `43.7s ~ 43.9s`
- `mean_gain_vs_single = 0.032424870721`

所以：

- gain 沒有消失
- 但比原始 bundle 的 `0.057159402144` 小

### 2. teacher split 結構真的變了

原始 split：

- `[[0,1,3,4,5,6],[2]]`
- 只有 `ue 15` 被 isolate

`P3.6m-2` 新 split：

- `[[0,1,3,4,6],[2,5]]`

對應原始 UE：

- 強組：`{0,1,2,3,5}`
- 弱組：`{15,4}`

也就是說：

- `ue 15` 不再是唯一弱者
- `ue 4` 被 teacher 視為值得一起拉出去分組的 decoy weak user

這是一個很重要的變化，因為它代表：

- 我們第一次在本來就有正增益的 family 上
- 成功把第二個 plausible weak candidate 注入進 teacher 決策本身

### 3. ambiguity 確實被加進來了

在正增益時刻 `43.7s ~ 43.9s`：

- `ue 15`
  - `cqi = 7`
  - `cost = 5.333333 ~ 5.500000`
- `ue 4`
  - `cqi = 15`
  - `cost = 3.333333`

`ue 4` 當然沒有弱到和 `ue 15` 一樣，但它已經不是完全普通的強用戶了。  
更重要的是：

- 它有輕微 cost penalty
- 又有 recent-decline history
- teacher 現在真的把它與 `ue 15` 放在同一個 group

這使得這個 regime 比原本的「單一明顯弱者」更適合當 learner challenge。

## 目前最重要的解讀

### 成功的地方

`P3.6m-2` 首次做到了這件事：

- 保住 teacher 的正增益 split
- 同時把第二個 decoy candidate 注入到 split 結構中

這比 `l-4` 更進一步，因為：

- `l-4` 只有 split structure，沒有 gain
- `m-2` 同時有 split structure 和 positive gain

### 還不夠的地方

目前這個 regime 還不是「完美 ambiguity」：

- `ue 15` 還是明顯最弱
- gain 也從 `0.0571` 降到 `0.0324`

也就是說：

- 我們確實把 decoy 加進來了
- 但 decoy 的加入會侵蝕一部分原始 gain basin

## 結論

`P3.6m-2` 是到目前為止最接近研究目標的 regime 之一：

- 它不像 `1|2|4|5` 那樣只有 split 結構
- 也不像原始 `0|1|15|2|3|4|5` 那樣只是單弱者 isolation

它現在位在兩者中間：

- 有真實正增益
- 也有被注入的第二個 decoy weak user

這使它成為下一步 learner-side 驗證的最佳候選。

## 建議下一步

最合理的下一步是直接進 `P3.6m-3`：

- 以 `43.7s ~ 43.9s` 的新正增益 segment 為中心
- 跑 focused temporal learner / ablation
- 檢查：
  - `teacher`
  - `LE-GRA`
  - `multi-feature`
  - `no-group`

是否終於在這條新 regime 上拉開差距
