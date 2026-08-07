# P3.6q-4 ~ q-8: structural bridge progress on `3|4|5|6 @ gnb_2`

## 背景

在 `P3.6q-1 ~ q-3` 之後，我們已經知道兩件事：

1. repo 內幾乎沒有乾淨且未探索的新 positive family
2. 單純手工堆出 three-group ladder，仍不足以在晚段自然形成 `3-group`

所以這一段改成另一條更務實的主線：

- 不再直接追求「一次做出 3-group」
- 先用可重複的 declarative scaffold，穩定地把 teacher-positive split
  從短片段擴成更長的 temporal bridge
- 再觀察這些 bridge 是不是 learner-hard，或只是 teacher-side 更穩而已

## 新工具：declarative family-window scaffold

新增：

- `build_family_window_transform_bundle.py`
- `p3_6q6_family_transform_spec_template.json`

用途：

- 針對指定 family、指定時間窗、指定 UE 規則做結構化 bundle 轉換
- 避免每一輪都再寫一個一次性的 bundle builder

這代表後續的資料生成不再是 scattered local tweak，而是可被重播的
spec-driven structural design。

## q-6: first real multi-phase positive family

規格：

- `p3_6q6_three_phase_ladder_spec.json`
- output: `p3_6q6_three_phase_ladder_bundle/`
- audit: `p3_6q6_teacher_audit/`

關鍵結果：

- family `3|4|5|6 @ gnb_2` 出現兩段不同 weak identity 的 positive split
- `25.8, 26.2`
  - split = `[[0,1,3],[2]]`
  - 實際上是 isolate `ue5`
  - gain = `0.09440267226723498`
- `27.1 ~ 27.3`
  - split = `[[0,2,3],[1]]`
  - 實際上是 isolate `ue4`
  - gain = `0.044402672267235155`

意義：

- 這是第一次在同一個 family 上，穩定看到「weak user 身分隨時間切換」
- 代表這個 family 不是只有單一弱側，而是可以承載 temporal crossover

限制：

- `27.4` 之後立刻掉回 single-group
- 也就是說，真正的問題不是「有沒有 positive split」，而是
  `ue4`-isolation regime 的存活太短

## q-7: naive extension does not move the cliff

規格：

- `p3_6q7_extend_mid_split_spec.json`
- output: `p3_6q7_extend_mid_split_bundle/`
- audit: `p3_6q7_teacher_audit/`

結果：

- positive snapshots 幾乎與 `q6` 相同
- `27.1 ~ 27.3` 的 `ue4`-isolation 沒有被有效延長

解讀：

- cliff 並不是因為晚段規格「太短」而已
- 它更像是一個局部結構斷點，需要在 `27.4+` 附近做 targeted bridge

## q-8: first successful bridge-window extension

規格：

- `p3_6q8_bridge_window_nudge_spec.json`
- output: `p3_6q8_bridge_window_nudge_bundle/`
- audit: `p3_6q8_teacher_audit/`

策略：

- 保留 `q6` 早段 `ue5` positive phase
- 保留 `q6` 中段 `ue4` positive phase
- 只針對 `27.4 ~ 27.6` 做最小 bridge nudge

teacher 結果：

- `25.8, 26.2`
  - split = `[[0,1,3],[2]]`
  - isolate `ue5`
  - gain = `0.09440267226723498`
- `27.1 ~ 27.6`
  - split = `[[0,2,3],[1]]`
  - isolate `ue4`
  - gain = `0.044402672267235155`

與 `q6/q7` 相比：

- `ue4`-isolation phase 從 `27.1 ~ 27.3` 成功延長到 `27.1 ~ 27.6`
- 也就是把 cliff 往後推了 3 個 snapshot

這是目前 `P3.6q` 最重要的 teacher-side 突破。

## focused learner result on q-8

Artifacts：

- `p3_6q8_kmeans_learner/`
- `p3_6q8_hybrid_learner/`

Focused setup：

- family = `3|4|5|6`
- train end = `27.3`
- test = `27.4 ~ 27.6`

結果：

- `No grouping` = `0.6471841780840183`
- `CQI k-means` = `0.6767859595955085`
- `Resource-cost k-means` = `0.6915868503512534`
- `Multi-feature k-means` = `0.6915868503512534`
- `Offline teacher` = `0.6915868503512534`
- `LE-GRA MVP` = `0.6915868503512534`

另外：

- pairwise accuracy = `1.0`
- ARI = `1.0`
- NMI = `1.0`

結論：

- `q8` 證明 teacher-positive bridge 可以被延長
- 但這段 bridge 並不 learner-hard
- 甚至 resource / multi-feature baseline 已經能完全 match teacher

## 研究意義

這一輪的價值不是「已經把 gap 拉大」，而是更精確地把問題拆開：

1. teacher-side survival 可以被局部 bridge 設計推動
2. learner-side hardness 不會因為單純延長同一個 split 就自然出現
3. 下一步需要的是：
   - 保留 teacher-positive 結構
   - 同時刻意加入 decoy / ambiguity / conflicting feature cues
   - 讓 baseline 更容易跟錯 weak identity 或 grouping boundary

## 下一步

最值得做的不是再做單純延長，而是 `q9` 類型設計：

- 目標仍是保住 `ue4`-isolation 的正增益
- 但要讓 `ue5/ue6` 在 CQI / history / resource cost 中呈現更強 decoy
- 觀察是否能形成：
  - teacher 仍 split `ue4`
  - 但 snapshot-driven baseline 更容易選錯到 `ue5` 或邊界 pair

如果 `q9` 仍然容易被 baseline 解掉，就代表：

- 問題不只是 bridge 長度不夠
- 而是我們需要更根本的 structure-level redesign，甚至新的 raw family
