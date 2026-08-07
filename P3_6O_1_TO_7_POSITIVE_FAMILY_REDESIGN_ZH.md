# P3.6o-1 ~ P3.6o-7 Positive-Family / New-Family Redesign

日期：2026-08-07

## 目的

在 `n` 系列之後，我們已經確認：

- `3|4|5|6 @ gnb_2` 可以造出新 teacher-positive regime
- 但 late `{ue4, ue5}` weak-pair 很難撐成新的 hard regime

所以 `o` 系列改做兩條平行探索：

1. 開新的 near-miss family，看能不能從頭造出 split structure
2. 回到本來就有正增益的 family，做 decoy / pair-candidate injection

## O1: 新 family focused audit

輸出：

- `p3_6o1_family_focus/`

目標 family：

- `2|3|4|5 @ gnb_2`
- `24.0s ~ 24.9s`

結果：

- `max_teacher_gain_vs_single = 0.0`
- `max_cqi_range = 4.0`
- `max_resource_cost_range = 0.5`
- `max_previous_quality_range = 0.0`

輪廓：

- `ue4` 本來就偏弱
- 但 family 整體沒有自然正增益

## O2: 新 family 第一版 primary-weak generator

腳本：

- `build_p3_6o2_primary_weak_bundle.py`

輸出：

- `p3_6o2_primary_weak_bundle/`
- `p3_6o2_teacher_audit/`
- `p3_6o2_focus_mining/`

設計：

- family：`2|3|4|5 @ gnb_2`
- `ue4`：primary weak
- `ue3`：light decoy

結果：

- `24.0s ~ 24.9s` 全部仍是 single-group
- `positive count = 0 / 10`
- `multigroup count = 0 / 10`

結論：

- 這條新 family 第一版連 split structure 都長不出來
- 不值得在 `o2` 附近做小幅度微調

## O3: 回到 positive family 的 focused audit

輸出：

- `p3_6o3_family_focus/`

目標 family：

- `0|1|2|3|4 @ gnb_2`
- `17.0s ~ 20.9s`

關鍵正增益窗口：

- `18.7s ~ 19.2s`
- teacher split：`[[0, 1, 2, 4], [3]]`
- 語意：穩定 isolate `ue3`
- `teacher_gain_vs_single = 0.011900924527038947`

這條 family 的重要價值：

- 它本來就有真的 positive-gain basin
- 很適合做 decoy injection，而不是從零硬造 split

## O4: light decoy injection

腳本：

- `build_p3_6o4_positive_family_decoy_bundle.py`

輸出：

- `p3_6o4_positive_family_decoy_bundle/`
- `p3_6o4_teacher_audit/`
- `p3_6o4_focus_mining/`

設計：

- 保留 `ue3` 當 primary weak
- 把 `ue4` 注入成 light temporal decoy

結果：

- `18.7s ~ 19.2s` 六個 target scenarios 全部仍是：
  - `[[0, 1, 2, 4], [3]]`
- `positive count = 6 / 6`
- `multigroup count = 6 / 6`

結論：

- 正增益 basin 非常穩
- 但 light decoy 還拉不動 structure

## O5: stronger decoy injection

腳本：

- `build_p3_6o5_stronger_decoy_bundle.py`

輸出：

- `p3_6o5_stronger_decoy_bundle/`
- `p3_6o5_teacher_audit/`
- `p3_6o5_focus_mining/`

設計：

- 把 `ue4` 從 light decoy 推成 stronger boundary decoy

結果：

- 仍然完全保持：
  - `[[0, 1, 2, 4], [3]]`
- `positive count = 6 / 6`
- `multigroup count = 6 / 6`

結論：

- `0|1|2|3|4 @ gnb_2` 的正增益窗口很穩
- 但單靠 stronger decoy 還不夠改變 teacher structure

## O6: pair-candidate injection

腳本：

- `build_p3_6o6_pair_candidate_bundle.py`

輸出：

- `p3_6o6_pair_candidate_bundle/`
- `p3_6o6_teacher_audit/`
- `p3_6o6_focus_mining/`

設計：

- 把 `ue4` 從 decoy 再往 true pair-candidate 推進
- 同時保留 `ue3` 當 primary weak

結果：

- teacher 第一次不再維持原本的 `ue3-only` split
- 但進入的是 tie-utility multigroup structure：
  - `18.7s ~ 19.1s`: `[[1, 2], [0, 3, 4]]`
  - `19.2s`: `[[0, 2], [1, 3, 4]]`
- `teacher_gain_vs_single ≈ 0`
- `positive count = 0 / 6`
- `multigroup count = 6 / 6`
- `positive_segment_count = 0`
- `near_miss_family_count = 1`

結論：

- `o6` 是這輪最重要的 structural breakthrough
- 它證明這條 positive family 其實可以被拉離 `ue3-only`
- 但目前拉出來的是 wrong / arbitrary tie split，不是真正可用的正增益 weak pair

## O7: true dual-weak pair attempt

腳本：

- `build_p3_6o7_dual_weak_pair_bundle.py`

輸出：

- `p3_6o7_dual_weak_pair_bundle/`
- `p3_6o7_teacher_audit/`
- `p3_6o7_focus_mining/`

設計：

- 不再只把 `ue4` 當 decoy
- 直接把 `ue3` 與 `ue4` 都塑造成 dual-weak pair

結果：

- teacher 又回到原本穩定的正增益結構：
  - `[[0, 1, 2, 4], [3]]`
- `positive count = 6 / 6`
- `multigroup count = 6 / 6`
- `candidate_temporal_slices.csv` 再度恢復正常正向 segment

結論：

- 把 `ue4` 正式推成 dual-weak pair，反而沒有保留 `o6` 的 structure shift
- 這代表目前存在一個很清楚的張力：
  - `o4 / o5 / o7`：保住 positive gain，但 structure 不動
  - `o6`：structure 會動，但 gain 掉到 tie

## 目前最重要結論

`0|1|2|3|4 @ gnb_2` 目前是新的高價值 family，因為它給了我們一個非常清楚的研究邊界：

1. positive-gain basin 很穩
2. decoy 太弱時，teacher structure 不動
3. pair-candidate 太強時，teacher structure 會動，但只到 tie split
4. 真 dual-weak 設計再拉回去時，teacher 又退回原本的 `ue3-only` 正增益解

換句話說，這條 family 比 `3|4|5|6 @ gnb_2` 更接近我們要的研究問題：

- teacher structure 是可擾動的
- 但 gain / structure 兩者目前還無法同時成立

## O8: localized gain recovery breakthrough

腳本：

- `build_p3_6o8_gain_recovery_bundle.py`

輸出：

- `p3_6o8_gain_recovery_bundle/`
- `p3_6o8_teacher_audit/`
- `p3_6o8_focus_mining/`

設計：

- 以 `o6` 為基底
- 把 `ue0` 明確往 strong cluster 拉回去
- 同時把 `ue4` 再局部加深一點
- 目標是保留 `o6` 的 structure-shift 方向，但恢復正增益

結果：

- `18.7s`
  - teacher split = `[[0, 1, 2], [3, 4]]`
  - 語意：第一次出現我們真正想要的 `{ue3, ue4}` weak pair
  - `teacher_gain_vs_single = 0.012637245583141055`
- `18.8s ~ 19.2s`
  - teacher 回到 single-group

結論：

- `o8` 是目前最重要的新突破
- 它第一次同時滿足：
  - 可解釋的 `{ue3, ue4}` weak pair
  - 真正的正增益
- 但目前只出現在單一 timestamp，還不是穩定 segment

## O9: pair stabilization

腳本：

- `build_p3_6o9_pair_stabilization_bundle.py`

輸出：

- `p3_6o9_pair_stabilization_bundle/`
- `p3_6o9_teacher_audit/`
- `p3_6o9_focus_mining/`

設計：

- 從 `o8` 出發
- 再稍微把 `ue0` 往 strong cluster 拉一點
- 再把 `ue4` 只小幅加深，試圖把 `o8` 的單點成功拉成短 segment

結果：

- 結果與 `o8` 相同：
  - `18.7s`: `[[0, 1, 2], [3, 4]]`, gain `0.012637245583141055`
  - `18.8s ~ 19.2s`: single-group

結論：

- `o9` 沒有把 `o8` 的單點成功進一步延長
- 但它也沒有把 `o8` 的 pair breakthrough 破壞掉
- 目前最合理的描述是：
  - 我們已經找到 `{ue3, ue4}` positive split 的 seed point
  - 但還沒把它擴成可訓練的 focused positive segment

## O10: local smoothing follow-up

腳本：

- `build_p3_6o10_local_smoothing_bundle.py`

輸出：

- `p3_6o10_local_smoothing_bundle/`
- `p3_6o10_teacher_audit/`
- `p3_6o10_focus_mining/`

設計：

- 以 `o8` 為基底
- 只對 `18.8s ~ 19.2s` 做局部平滑：
  - 把 strong side 的 `ue0 / ue1` 再稍微拉高
  - 把 `ue4` 再略微加深
- 目標是把 `o8` 的單點 pair success 拉成至少兩個以上連續 timestamp

結果：

- `18.7s` 仍然保持：
  - `[[0, 1, 2], [3, 4]]`
  - `teacher_gain_vs_single = 0.012637245583141055`
- `18.8s ~ 19.2s` 仍全部回到 single-group
- `positive_segment_count = 1`
- `segment = 18.7s ~ 18.7s`

結論：

- `o10` 沒有把 `o8` 的單點成功延長成短 segment
- 這說明目前不是一般局部平滑不夠，而是：
  - `o8` 的 `{ue3, ue4}` positive split 目前真的只存在於非常窄的局部條件

## 更新後的判斷

現在最精準的研究描述是：

- 我們已經找到第一個可重現的 `{ue3, ue4}` positive split seed point
- 但這個 seed point 在 `18.7s` 之外會立刻崩回 single-group
- 因此下一步要嘛：
  - 做更細的 timestamp-local shaping
  - 要嘛直接承認它是 single-point regime，先做超短窗 learner-side validation

## 下一步建議

最值得做的下一步不是再做一般 decoy 微調，而是：

1. 以 `o8` 為中心做 timestamp-neighborhood stabilization
   - 不要再回頭做 broad family search
   - 直接在 `18.7s` 附近做 very local smoothing
2. 先做 focused teacher-side validation
   - 不要先擴 learner matrix
3. 如果能在 `o8` 附近造出：
   - multigroup
   - positive gain
   - 且 weak-group 語意可解釋
   才值得進 focused learner holdout
