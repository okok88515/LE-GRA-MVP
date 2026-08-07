# P3.6m-30 family-bank filter fix and next-target triage

交接日期：2026-08-07

## 這一步要解決的問題

`P3.6m-29` 已經把目前 focused regimes 分成：

- `m2`：easy / already-solvable
- `m4b`：bridge-needed

接下來理論上應該從 `p3_6m_family_bank/` 找下一條高資訊量 family，
用來判斷：

- 是否存在第三條 genuinely unsolved regime
- 或至少存在另一條新的 bridge-needed regime

但在開始挑 candidate 時，我們發現一個更根本的問題：

- family bank 裡不同 family 的 `candidate_temporal_slices.csv`
- 竟然大量重複，內容看起來像在指向同一批正例

這代表在拿它做下一步判斷之前，必須先確認 mining pipeline 本身是不是有 target-family 汙染。

## 問題診斷

### 異常現象

在原始 `p3_6m_family_bank/` 中：

- `rank1_1_2_4_5_gnb_2_focus_mining/candidate_temporal_slices.csv`
- `rank4_0_1_15_2_3_4_gnb_1_focus_mining/candidate_temporal_slices.csv`
- `rank5_31_4_5_6_7_gnb_2_focus_mining/candidate_temporal_slices.csv`

這三份檔案的 hash 完全相同。

同樣地：

- 這三份 `positive_segments.csv`

hash 也完全相同。

這不是正常的現象，因為它們對應的是不同 family。

### 原因

檢查程式後發現：

- `run_p3_6m_family_bank.py`
  會先對每個 family 建 bundle、跑 teacher audit
- 但接著呼叫 `mine_focus_slices.py` 時
  只傳了整份 `scenario_teacher_decisions.csv`
  沒有把：
  - `target_ue_ids`
  - `serving_gnb`
  當成 filter 傳進去

所以 `mine_focus_slices.py` 實際上是在整個 audit CSV 上挖正例，
不是只挖那個 family 自己的 rows。

這會導致：

- 某個 family 的 focus mining 輸出
- 被 bundle 內其他 family 的正例污染

## 修正內容

### 1. `mine_focus_slices.py`

新增可選參數：

- `--target-ue-ids`
- `--target-serving-gnb`

並在 `load_rows(...)` 階段直接過濾：

- `ue_ids`
- `serving_gnb`

只有完全匹配 target family 的 rows 才會被保留下來。

### 2. `run_p3_6m_family_bank.py`

在呼叫 `mine_focus_slices.py` 時，現在會明確傳入：

- `--target-ue-ids <family ue_ids>`
- `--target-serving-gnb <family gnb>`

這樣每個 family 的 focus mining 才是真正 family-conditioned 的。

## 驗證方式

我沒有覆蓋原本輸出，而是重跑到新的目錄：

- `p3_6m_family_bank_filtered/`

命令：

```bash
python -u run_p3_6m_family_bank.py \
  --out-dir p3_6m_family_bank_filtered \
  --top-k 5
```

## 修正後的結果

新的 summary：

- `p3_6m_family_bank_filtered/family_bank_summary.csv`

關鍵結果如下：

### `rank2 = 0|1|15|2|3|4|5 @ gnb_1`

這就是目前已知的 `m4b` 主 family。

它仍然是唯一真正有 target positive gain 的候選：

- `target_positive_gain_count = 3`
- `target_max_gain_vs_single = 0.057159402144`
- `focus_positive_segment_count = 1`

而且它的 `candidate_temporal_slices.csv` 不再是空的。

### 其他 family

修正後的：

- `rank1 = 1|2|4|5 @ gnb_2`
- `rank3 = 3|4|5|6 @ gnb_2`
- `rank4 = 0|1|15|2|3|4 @ gnb_1`
- `rank5 = 31|4|5|6|7 @ gnb_2`

全部都變成：

- `target_positive_gain_count = 0`
- `target_max_gain_vs_single = 0`
- `focus_positive_segment_count = 0`
- `candidate_temporal_slices.csv` 為空

也就是說：

- 這些 family 也許有 multi-group 結構或 near-miss 特徵
- 但在目前的 target family 視角下
- 它們沒有形成真正的 teacher-positive temporal slice

## 這一步最重要的結論

### 1. 原始 family bank 不能直接用來選下一個 regime

因為它的 focus mining 曾經被全 bundle 正例污染。

如果沒有這次修正，我們很容易誤以為：

- `rank1`
- `rank4`
- `rank5`

都各自帶有與 `m4b` 類似的正向 temporal slice。

但修正後發現不是。

### 2. 修正後的 family bank 並沒有提供新的第三條高資訊量 family

這是目前最重要的研究判讀。

不是我們還沒跑到，而是：

- 在現有 top-5 candidate bank 裡
- 除了已知的 `m4b`
- 沒有其他 family 同時滿足：
  - target-positive gain
  - 可切的 positive temporal slice
  - 可作為 focused learner 驗證的 regime

### 3. 下一步應該從「修 learner」轉成「找新 regime source」

到這裡為止，最值得做的事情已經不是：

- 再拿同一批 family bank 做小 tweak
- 或在空的 candidate 上硬跑 learner

而是要承認：

- 目前這個 family bank 已經沒有新的高資訊量 candidate 可挖

所以真正合理的下一步會是：

1. 換新的 ranking source
2. 或放寬 mining criterion，改找：
   - stronger near-miss families
   - multi-group but zero-gain structural families
   - longer temporal windows that may turn near-miss into positive segments

## 對專案方向的實際意義

這一步很重要，因為它避免了我們再度陷入：

- 看起來有很多 family 可做
- 其實只是被同一條 `m4b` 正例污染

現在比較誠實的研究狀態是：

- `m2`：已解
- `m4b`：已找到 bridge-needed 解法
- 現有 family bank：暫時沒有新的第三條 focused hard regime

所以之後若要把 teacher、LE-GRA、baseline 的差距再拉大，
最可能有用的方向不是同一批資料上的再微調，
而是重新生成或重新挖掘新的 informative regime。

## 小結

`P3.6m-30` 的核心價值有兩個：

1. 修掉 family-bank focus mining 的 target-filter bug
2. 證明修正後的 top-5 family bank 中，
   只有已知的 `m4b` 仍然是一條真正的 positive focused regime

這讓下一步變得非常清楚：

- 不要再把現在這批 family bank 當成還有很多新 regime 可以直接做
- 該開始找新的 scenario source / ranking source
