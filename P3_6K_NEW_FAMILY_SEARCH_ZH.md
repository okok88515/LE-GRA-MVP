# P3.6k New Family Search

Last updated: 2026-08-06

## 目標

在 `P3.6j-2c ~ j-2f` 之後，我們已經很清楚：

- `seg_01` 這條 `0|1|15|2|3|4|5 @ gnb_1` family 有明顯 plateau
- 繼續在同一家族上疊 cost-side 訊號，不是回到 plateau，就是直接 collapse
- 而且目前仍然沒有任何 `teacher_group_count >= 3` 的例子

所以這一步的策略不再是繼續磨 `seg_01`，而是：

> 直接換 family / 換 scenario source  
> 去找新的 informative family

## 方法

新增腳本：

- `rank_family_redesign_candidates.py`

用途：

- 從 `scenario_teacher_decisions.csv` 讀出所有 family
- 預設只看 `teacher_gain_vs_single = 0` 的 near-miss families
- 依照下列訊號做 ranking：
  - `max_cqi_range`
  - `max_resource_cost_range`
  - `max_previous_quality_range`
  - `user_count`
  - `scenario_count`
  - `duration`

執行：

```powershell
python rank_family_redesign_candidates.py --audit-csv p3_6i2_teacher_audit/full_bundle/scenario_teacher_decisions.csv --out-dir p3_6k_family_ranking
```

輸出：

- `p3_6k_family_ranking/family_redesign_ranking.csv`
- `p3_6k_family_ranking/top10_family_redesign_ranking.csv`
- `p3_6k_family_ranking/summary.txt`

## Ranking 結果

Top 10 中，最值得優先處理的是：

1. `3|4|5|6 @ gnb_2`
2. `15|31 @ gnb_1`
3. `6|7 @ gnb_2`
4. `15|6|7 @ gnb_2`
5. `31|4|5|6 @ gnb_2`

其中第一名是：

- `3|4|5|6 @ gnb_2`
- `scenario_count = 42`
- `user_count = 4`
- `max_cqi_range = 6.0`
- `max_resource_cost_range = 0.833333`
- `max_previous_quality_range = 1.0`
- `time = 25.8s ~ 29.9s`

## 為什麼選 `3|4|5|6 @ gnb_2`

這個 family 比 `seg_01` 更值得下一步投入，原因有三個：

### 1. 結構不是「單一弱者 + 一群很像的人」

抽樣看前幾個 snapshot：

- `ue 3`: CQI 14~15, distance 約 109~111 m
- `ue 4`: CQI 12, distance 約 141~143 m
- `ue 5`: CQI 14, distance 約 156~157 m
- `ue 6`: CQI 14, distance 約 164 m

它的形狀更像：

- `ue 4` 是明顯較弱者
- `ue 5 / ue 6` 距離較遠但 CQI 又接近
- `ue 3` 相對強但不是像 `seg_01` 那樣完全壓倒性

這種結構更容易出現：

- competing split candidates
- cost / quality / distance 不完全對齊的 decision surface

### 2. 時間窗夠長

`25.8s ~ 29.9s` 橫跨：

- `42` 個 snapshot

這比很多只有 `0.4~0.9s` 的 near-miss family 好得多。  
代表我們有足夠 temporal support 去做：

- focused slice mining
- local redesign
- learner train/test slicing

### 3. 目前是 near-miss，但指標已經夠高

它現在還是 `teacher_gain_vs_single = 0`，但：

- `cqi_range` 高
- `resource_cost_range` 高
- `previous_quality_range` 也不是零

這很像一個「快要有 split，但還差一點結構訊號」的 family。  
比起已經被證明有 plateau 的 `seg_01`，它更適合拿來重新設計。

## 暫時放後面的候選

### `15|31 @ gnb_1`

雖然 `scenario_count` 很高，但它只有兩個 user。  
這比較不適合我們現在要追的方向，因為：

- 太容易退化成單切式 decision
- 更難觀察 richer split structure

### `31|4|5|6 @ gnb_2`

這個 family 也有價值，但只有：

- `5` 個 snapshot

它比較像 `3|4|5|6 @ gnb_2` 的短窗變體，暫時可以當 follow-up，不適合當主目標。

## 下一步建議

正式進入新的 family source：

### P3.6k-1

以 `3|4|5|6 @ gnb_2` 為新的主 family，先做：

1. focused audit  
2. temporal slice mining  
3. family-specific redesign hypothesis

優先檢查：

- `ue 4` 是否是穩定弱點
- `ue 5 / ue 6` 是否能形成 competing split candidates
- 在這個 family 上，cost-side 與 previous-quality-side 哪一邊更值得先推

## 一句話結論

`P3.6k` 的結果是：我們正式停止在 `seg_01` plateau 上加料，並把下一個主戰場切換到 `3|4|5|6 @ gnb_2`，因為它是目前 near-miss families 裡最有潛力被重新設計成新 informative regime 的候選。 
