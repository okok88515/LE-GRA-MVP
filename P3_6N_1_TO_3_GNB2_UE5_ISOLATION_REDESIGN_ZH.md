# P3.6n-1 ~ P3.6n-3 `3|4|5|6 @ gnb_2` ue5-isolation redesign

交接日期：2026-08-07

## 背景

在 `P3.6m-30` 修正 family-bank target filter 之後，我們確認：

- 現有 `p3_6m_family_bank` 裡
- 除了已知的 `m4b`
- 沒有新的 target-positive focused family

因此下一步不再是直接從現有 family bank 挖 learner，
而是要主動把高結構壓力的 near-miss family 改造成新的 informative regime。

最合理的候選就是先前已被 redesign ranking 選中的：

- `3|4|5|6 @ gnb_2`

它的特徵是：

- `scenario_count = 42`
- `time_window = 25.8s ~ 29.9s`
- `max_cqi_range = 6.0`
- `max_resource_cost_range = 0.833333`
- 但 `max_teacher_gain_vs_single = 0`

也就是：

- 結構壓力明顯存在
- 但 teacher 仍然不願意 split

## 核心假設

根據 `p3_6k1_family_focus` 的舊分析：

- `ue5` 本來就像 late-window 的弱者
- 但 `previous_quality` 幾乎是平的

所以我們的假設是：

- 這個 family 缺的不是更多瞬時 CQI 差異
- 而是更強的「持續弱者」證據
- 同時可能也需要更緊的 resource pressure

## P3.6n-1：continuity gap only

新 script：

- `build_p3_6n1_quality_gap_bundle.py`

輸出：

- `p3_6n1_quality_gap_bundle/`
- `p3_6n1_teacher_audit/`

改法：

- 只針對 `25.8s ~ 29.9s` 的 `3|4|5|6 @ gnb_2`
- 不改整體拓樸
- 主要改 `users.csv`

具體做法：

- `ue5`
  - `previous_quality = 1`
  - recent CQI history 下修，做成持續弱者
- `ue3 / ue4 / ue6`
  - `previous_quality = 4`
  - history 保持平滑穩定

結果：

- teacher 仍然全部 single-group
- `positive_segment_count = 0`

解讀：

- continuity gap 單獨存在還不夠

## P3.6n-2：continuity gap + moderate pressure

新 script：

- `build_p3_6n2_quality_gap_pressure_bundle.py`

輸出：

- `p3_6n2_quality_gap_pressure_bundle/`
- `p3_6n2_teacher_audit/`
- `p3_6n2_focus_mining/`

改法：

- 保留 `n1` 的 continuity gap
- 再加上：
  - target window `rb_available: 7 -> 5`
  - `ue5` RB rates 進一步下修
  - `ue5` 現時 CQI 再弱化

直接結果：

- teacher 仍然全部 single-group
- `positive_segment_count = 0`

但這一步不是沒價值。

額外做的 teacher-gap 診斷顯示：

- base bundle：
  - `mean_best_non_single_gap = -0.074539932885`
- `n1`：
  - `mean_best_non_single_gap = -0.079071102954`
- `n2`：
  - `mean_best_non_single_gap = -0.031232104943`

而且最佳非單群 split 已經穩定成：

- `[[0,1,3],[2]]`

也就是：

- 把 `ue5` 單獨隔離

解讀：

- 方向是對的
- 只是壓力還不夠大到跨過 teacher threshold

## P3.6n-3：strong ue5 isolation regime

新 script：

- `build_p3_6n3_isolate_ue5_bundle.py`

輸出：

- `p3_6n3_isolate_ue5_bundle/`
- `p3_6n3_teacher_audit/`
- `p3_6n3_focus_mining/`

改法：

從 `n2` 再往前推：

- target window `rb_available: 5 -> 4`
- `ue5` RB rates 再大幅下修
- `ue5` 現時 CQI 再下修
- `ue5` 的 recent history 進一步往持續弱者推

## 關鍵結果

`n3` 出現明確突破：

- `3|4|5|6 @ gnb_2`
- 在 `25.8s ~ 29.9s`
- teacher 全段都改成：
  - `teacher_group_count = 2`
  - `teacher_groups = [[0,1,3],[2]]`
- 也就是穩定把 `ue5` 單獨隔離

而且：

- `teacher_gain_vs_single = 0.079451741871`

幾乎整段 window 都是固定正值。

focus mining 結果：

- `positive_segment_count = 1`
- `candidate_temporal_slice_count = 41`
- `near_miss_family_count = 0`

也就是：

- 它已經不再是 near-miss
- 而是新的完整 positive regime

## 這一步最重要的意義

### 1. 我們成功做出了新的 teacher-positive scenario source

這是目前最重要的突破。

在 `m4b` 之外，我們現在不只是在舊資料裡找新的 regime，
而是已經能把高結構壓力 family 主動改造成新的正向 regime。

### 2. 單純 continuity 不夠，moderate pressure 也不夠，但更強的 localized isolation 夠

`n1 -> n2 -> n3` 的序列很有研究價值：

- `n1`：
  continuity-only 不夠
- `n2`：
  continuity + 中度 pressure 仍不夠
- `n3`：
  當 `ue5` isolation 夠強時，teacher 穩定 split

這說明：

- teacher 需要的不是模糊的弱者傾向
- 而是足夠明確、足夠持續、而且在資源壓力下有實際代價的弱者結構

### 3. split 形式本身也很乾淨

`n3` 不是隨便出現多群，
而是穩定地選：

- `[[0,1,3],[2]]`

這對後續 learner 很重要，因為：

- supervision target 乾淨
- weak group identity 穩定
- temporal slice 很長

這比只在單一 snapshot 偶然 split 更適合做 focused learner 驗證。

## 下一步建議

最合理的下一步已經很清楚：

1. 以 `p3_6n3_isolate_ue5_bundle` 為新的 focused regime
2. 先做 focused learner baseline：
   - 舊 `kmeans_embedding`
   - `membership_order`
   - 看這條新 regime 屬於：
     - easy
     - bridge-needed
     - 或新的 genuinely unsolved learner regime
3. 如果 learner 也能在這裡拉出 teacher / baseline gap，
   就能把研究從單一 `m4b` 主線，擴展成至少兩條不同來源的 informative regime

## 小結

`P3.6n-1 ~ P3.6n-3` 的最終結論是：

- `3|4|5|6 @ gnb_2` 原本只是 near-miss
- 但經過連續三輪 localized redesign
- `n3` 已成功把它推成新的 teacher-positive focused regime

而且它的結構非常清楚：

- 弱者是 `ue5`
- 穩定 split 是 `[[0,1,3],[2]]`
- 正增益在整段 `25.8s ~ 29.9s` 都成立

這是目前 `m4b` 之外，最值得立刻接著做 learner 驗證的新主線。
