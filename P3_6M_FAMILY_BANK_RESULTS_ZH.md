# P3.6m family-bank batch search

## 目的

`P3.6l-4` 已經證明 `1|2|4|5 @ gnb_2` 可以做出「有 split 結構但沒有正增益」的
dual-candidate family。  
`P3.6m` 的目標不是再手工調同一條 family，而是把這個
`primary weak + light decoy` 模板批次套到多個候選 family，確認：

1. 哪些 family 能被推成真正的正增益 split。
2. 哪些 family 至少能長出穩定的 multi-group 結構。
3. 哪些 family 對這種模板完全沒有反應。

## 新增腳本

- `run_p3_6m_family_bank.py`

這支腳本會：

1. 讀 `p3_6l_dual_candidate_ranking_v2/top10_dual_candidate_family_ranking.csv`
2. 對每個候選 family 建 bundle
3. 套用通用模板
   - `candidate_1 -> primary weak`
   - `candidate_2 -> light decoy`
4. 依序跑
   - `run_p3_6_teacher_decision_audit.py`
   - `mine_focus_slices.py`
5. 匯總成
   - `p3_6m_family_bank/family_bank_summary.csv`

## 本輪測試 family

本輪先測 5 個 rank：

- rank 1: `1|2|4|5 @ gnb_2`
- rank 2: `0|1|15|2|3|4|5 @ gnb_1`
- rank 4: `0|1|15|2|3|4 @ gnb_1`
- rank 5: `31|4|5|6|7 @ gnb_2`
- rank 9: `0|1|2|3|4 @ gnb_2`

## 核心結果

最新彙總檔：

- `p3_6m_family_bank/family_bank_summary.csv`

重點如下：

### 1. `1|2|4|5 @ gnb_2` 仍然是最好的 structural-split family

- `window = 23.0s ~ 23.9s`
- `window_multi_group_count = 6`
- `window_positive_gain_count = 0`

實際 teacher 行為：

- `23.3s ~ 23.8s` 出現 split
- split 結構為 `[[0,3],[1,2]]`
- 對應原始 UE 為 `{1,5}` vs `{2,4}`

這代表：

- 這條 family 真的能支撐 dual-candidate split 結構
- 但它仍然卡在 tie-utility plateau
- 它適合拿來研究「怎麼讓 learner 分錯」
- 不適合再拿來期待自然長出更大的 teacher gain

### 2. `0|1|15|2|3|4|5 @ gnb_1` 沒有被新模板推動

- `window = 38.0s ~ 43.6s`
- `window_multi_group_count = 0`
- `window_positive_gain_count = 0`

雖然 summary 裡面仍可看到：

- `target_positive_gain_count = 3`
- `target_max_gain_vs_single = 0.057159402144`

但那不是 `P3.6m` 新做出來的效果，而是原本 base bundle 就存在的既有正增益段：

- `43.7s ~ 43.9s`
- split `[[0,1,3,4,5,6],[2]]`
- 被隔離的是 local index `2`，也就是 `ue 15`

所以這條 family 的正確解讀是：

- 它本來就有一段很強的單弱用戶正增益 regime
- 但在我們這次改動的 near-miss window 裡，通用 dual-candidate 模板沒有把它提早推成 split

### 3. 其餘 family 幾乎完全沒有反應

- `0|1|15|2|3|4 @ gnb_1`
- `31|4|5|6|7 @ gnb_2`
- `0|1|2|3|4 @ gnb_2`

在各自 window 內都是：

- `window_multi_group_count = 0`
- `window_positive_gain_count = 0`

其中 `0|1|2|3|4 @ gnb_2` 很值得注意：

- base bundle 原本在 `18.7s ~ 19.2s` 有正增益 split
- 但套上這個 family-bank 模板後，`17.0s ~ 20.9s` 全部退回 single-group

這表示：

- 並不是所有本來有 split 潛力的 family 都適合同一種模板
- 有些 family 對 decoy 的加入非常脆弱
- 模板一旦破壞原本的「單一明顯弱者」幾何，teacher 反而直接回 single-group

## 本輪 insight

### Insight 1: 通用模板可以複製 split「結構」，但很難複製正增益「經濟性」

`1|2|4|5` 證明結構可以被做出來。  
但只要想把它推成更高 gain，或把同樣模板套到別的 family，上述 split 就很容易：

- 變成 tie split
- 或直接 collapse 回 single-group

這表示真正困難的不是「讓 teacher 分兩群」，而是：

- 讓 split 在 utility 上持續比 single-group 更好

### Insight 2: 現在最有價值的 source family 分成兩類

第一類是 `1|2|4|5 @ gnb_2`：

- 適合做 dual-candidate ambiguity
- 適合做「teacher 會 split，但 gain 很小」的 learner challenge

第二類是 `0|1|15|2|3|4|5 @ gnb_1`：

- 適合做明確正增益 split
- 但目前比較像單弱者 isolation family
- 不像真的 dual-candidate ambiguous family

也就是說，現在其實有兩條不同研究軸線：

1. ambiguity 軸：讓 static/multi-feature 更容易搞混，但 teacher 仍想 split
2. gain 軸：讓 teacher 的 split 經濟性真的拉開

目前這兩條軸線還沒有在同一個 family 上合流。

### Insight 3: 下一步不該再做同一種微調

`P3.6m` 的 batch 結果已經很明確：

- 單靠通用 `primary weak + light decoy` 模板
- 不足以把多數 near-miss family 推成新的正增益 regime

因此下一步比較合理的是：

1. 針對 `1|2|4|5` 做 learner-side separation challenge
   - 不再追求 teacher gain
   - 改追求讓 `LE-GRA` 和 `multi-feature` 拉開
2. 或者換新 scenario source
   - 專門找「本來就有較長 split window」的 family
   - 再做 dual-candidate ambiguity 注入

## 建議的 P3.6m-2 方向

我目前更推薦第二條：

- 不再只從 near-miss family 開始
- 改從「本來就有正增益 split」的 family 出發
- 然後往裡面注入第二個 decoy 弱者

最直接的候選就是：

- `0|1|15|2|3|4|5 @ gnb_1`

因為它已經證明 teacher 願意為 `ue 15` 做正增益 isolation。  
如果能在不破壞這個正增益的前提下，讓 `ue 4` 或另一個相近候選者變成看起來也像弱者，
就有機會第一次做出：

- teacher 仍然穩定 split
- 但 static / multi-feature 不再那麼容易複製 teacher

## 操作注意事項

- PowerShell 參數若包含 `|`，要用單引號包住，例如：
  - `--target-ue-ids '1|2|4|5'`
- 不要把 bundle 建置與 audit 並行跑在同一個輸出目錄上
  - 否則 audit 可能會讀到尚未寫完的 CSV
- `run_p3_6_teacher_decision_audit.py` 的 `--bundle-dir`
  - 要指向實際的 `.../bundle` 目錄
