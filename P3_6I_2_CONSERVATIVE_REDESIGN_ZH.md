# P3.6i-2 Conservative Targeted Redesign

Last updated: 2026-08-06

## 目標

P3.6i 的激進 targeted redesign 雖然試圖強化 northbound 使用者的速度差與分離度，
但最後把原本在 `rb_budget_ratio = 0.28` 附近出現的 positive-gain split family
整個洗掉了。P3.6i-2 的目的不是再更激進，而是反過來做一個保守修正版：

- 保留原本有效的車流重疊節奏
- 只對疑似關鍵族群做小幅速度調整
- 盡量把 `0,1,2,3,4,5,6,7,15,31` 這 10 個實際會進 bundle 的車輛關係保留下來

核心問題是：
> 如果我們不要破壞原本的 overlap / cross-traffic 結構，只做溫和的 targeted redesign，
> 能不能把 teacher 願意 split 的 regime 找回來？

## 實作內容

新增檔案：

- `p3_6i2_coupled_scenario/targeted_family_conservative.rou.xml`
- `p3_6i2_coupled_scenario/targeted_family_conservative.sumocfg`
- `p3_6i2_coupled_scenario/targeted_family_conservative.launchd.xml`
- `p3_6i2_coupled_scenario/omnetpp.ini`
- `p3_6i2_run_targeted_family_coupled.sh`
- `build_p3_6i2_coupled_bundle.py`

設計原則：

- 保留 northbound `0..7` 原本的發車節奏：`0.0, 0.2, ..., 1.4s`
- 不再像 P3.6i 那樣大幅拉開 spacing
- 只對 `1..6` 施加溫和 speed ladder，避免整個 platoon 被打散
- 其他 southbound / eastbound / westbound 流量維持近原始設計

這一版的假設很明確：

> informative split regime 不是單純靠「把人拉開」就會出現，
> 而是要保住原本會造成 ambiguity 與 resource-pressure tradeoff 的互動結構。

## 執行結果

### Coupled simulation

成功執行：

- script: `p3_6i2_run_targeted_family_coupled.sh`
- raw radio rows: `1,353,826`
- raw mobility rows: `3,249`

### Bundle

`build_p3_6i2_coupled_bundle.py` 結果：

- retained SUMO vehicles: `10`
- retained UE IDs: `0,1,2,3,4,5,6,7,15,31`
- bundle scenarios: `875`
- teacher scenarios: `875`

這點很重要，因為它和 `p3_6e` 的有效 UE 集完全一致，而不是像 P3.6i 那樣只剩 `0..7`。
也就是說，P3.6i-2 至少成功保住了原本 informative regime 的參與者集合。

### Teacher-decision audit

`p3_6i2_teacher_audit/full_bundle/summary.csv`：

- `scenario_count = 830`
- `multi_group_count = 9`
- `positive_gain_count = 9`
- `positive_gain_ratio = 0.01084`
- `max_teacher_gain_vs_single = 0.05716`

和 P3.6i 比較：

- P3.6i：`positive_gain_count = 0`
- P3.6i-2：`positive_gain_count = 9`

所以 conservative redesign 明確成功把 positive split 現象救回來了。

## Focus mining 結果

`p3_6i2_focus_mining/summary.txt`：

- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 7`
- `near_miss_family_count = 13`

兩段真正的 positive segments 是：

1. `0|1|15|2|3|4|5 @ gnb_1`
   - time: `43.7s ~ 43.9s`
   - snapshots: `3`
   - mean/max gain: `0.057159`
   - CQI range: `8`
   - resource-cost range: `2.1667 ~ 2.3333`
   - teacher split: `[[0,1,3,4,5,6],[2]]`

2. `0|1|2|3|4 @ gnb_2`
   - time: `18.7s ~ 19.2s`
   - snapshots: `6`
   - mean/max gain: `0.011901`
   - CQI range: `5 ~ 6`
   - resource-cost range: `1.0`
   - teacher split: `[[0,1,2,4],[3]]`

此外，`candidate_temporal_slices.csv` 已經自動整理出 7 個可直接拿去做下一輪
focused temporal learner 的切法。其中最值得優先測的是：

- `seg_02 / 0|1|2|3|4 @ gnb_2`
  - split around `18.8s ~ 19.0s`
  - train scenarios 約 `19~21`
  - test scenarios 約 `2~4`
- `seg_01 / 0|1|15|2|3|4|5 @ gnb_1`
  - split around `43.7s ~ 43.8s`
  - train scenarios 約 `58~59`
  - test scenarios 約 `1~2`

## 和前面結果的關係

P3.6i-2 給了三個很關鍵的研究訊號。

### 1. P3.6i 失敗不是因為 targeted redesign 這個方向本身錯

錯的是 redesign 太激進，破壞了原本有效的 traffic interaction。
當我們回到保守設計，positive split 就回來了。

### 2. informative regime 確實高度依賴「哪些車真的會進 bundle」

`p3_6e` 和 `p3_6i2` 都保留了同一組有效 UE：

- `0,1,2,3,4,5,6,7,15,31`

而 P3.6i 只剩：

- `0,1,2,3,4,5,6,7`

這幾乎直接解釋了為什麼 P3.6i 會把 positive split family 洗掉。
也就是說，cross-traffic 的 `15`、`31` 很可能不是背景雜訊，而是 informative regime 的一部分。

### 3. 新 positive family 不再只侷限於 `1|2|3|4|5|6 @ gnb_2`

P3.6i-2 出現了兩個新的正增益 family：

- `0|1|2|3|4 @ gnb_2`
- `0|1|15|2|3|4|5 @ gnb_1`

這代表 targeted redesign 不只是「把舊 family 救回來」而已，而是可能把 split regime
移到另一段更有辨識度的互動區間。這對下一輪 learner study 是好消息，因為我們現在有
不只一段候選 temporal slice 可以測。

## 研究解讀

目前最合理的解讀是：

> LE-GRA 可用的 split regime 不是完全不存在，而是對場景結構很敏感。
> 如果流量設計破壞了 overlap 與 cross-traffic，teacher 會重新偏向 single-group。
> 但只要保住這些互動，teacher 就會重新出現穩定且可挖掘的 split decision。

換句話說，這不是「演算法只能用在極少數特例」的直接證據，
而比較像是：

- 這個研究問題本來就只會在特定 pressure/ambiguity window 發生
- 我們需要更精準地把那種 window 設計出來並保留下來

## 下一步建議

P3.6i-2 完成後，最合理的順序是：

1. 先跑一輪 focused temporal learner on `seg_02`
   - 原因：它有 `6` 個 positive snapshots，train/test 切法也比 `seg_01` 穩定
2. 再跑 `seg_01`
   - 雖然 gain 較大，但 test window 太短，容易只剩 `1~2` 個 snapshots
3. 比較兩段 slice 上：
   - LE-GRA utility
   - teacher imitation
   - 是否能穩定學到「孤立單一差用戶」這種 split pattern

如果 `seg_02` 跟 `seg_01` 都能成功，就可以正式主張：

> 在 coupled real-trace-like regime 中，只要 train side 有對應的正增益 split supervision，
> LE-GRA 不只在單一 slice，而是在多個 focused temporal windows 上都能學到 teacher 的 split decision。

## Seg_02 Focused Temporal Learner 結果

`seg_02` 已實際跑完，使用設定：

- bundle: `p3_6i2_coupled_bundle/bundle`
- focus UE IDs: `0|1|2|3|4`
- train window end: `18.9s`
- test window: `19.0s ~ 19.2s`
- output: `p3_6i2_seg02_temporal_learner/`

split summary：

- background train scenarios: `552`
- focus train scenarios: `139`
- focus test scenarios: `3`
- focus train positive gain count: `3`
- focus test positive gain count: `3`

### Main comparison

測試結果非常乾淨：

- No grouping: `0.6072`
- CQI k-means: `0.6191`
- Resource-cost k-means: `0.6191`
- Multi-feature k-means: `0.6191`
- Offline teacher: `0.6191`
- LE-GRA MVP: `0.6191`

也就是說，LE-GRA 在這個 slice 上完全追上 teacher，且和 Multi-feature 一樣都達到最佳 utility。

### Teacher imitation

`teacher_imitation_diagnostics.csv` 顯示：

- Multi-feature: pairwise `1.0`, ARI `1.0`, NMI `1.0`
- LE-GRA: pairwise `1.0`, ARI `1.0`, NMI `1.0`

因此這不是只有 utility 剛好打平，而是 partition 結構也完全對齊 teacher。

### 解讀

`seg_02` 的結果把 P3.6g 的結論往前推了一步。

P3.6g 只能說：
- 在 `0|1|2|3` 那一段 focused window 上，只要 train side 有正增益 supervision，
  LE-GRA 可以學到 teacher。

現在 `seg_02` 進一步說明：
- 即使換成 conservative redesign 後的新 family `0|1|2|3|4 @ gnb_2`
- 即使正增益 window 只有 `3` 個 test snapshots
- 只要 train/test 都真的落在同一個 split regime 上，
  LE-GRA 仍然可以完整追上 teacher。

這代表目前最強的研究訊號不是「某一組 UE 很特殊」，而是：

> 真正決定 learner 成敗的，仍然是 supervision 是否對齊到真實存在的 split regime。

### 目前還不能過度解讀的地方

這段結果雖然漂亮，但還有兩個限制：

1. `seg_02` 的 test 只有 `3` 個 snapshots
2. Multi-feature 也同樣完美對齊 teacher

所以這一輪更像是：
- 再次驗證 protocol 是對的
- 再次證明 LE-GRA 沒有在這種 real-trace-like slice 上失效

但它還不足以單獨證明 LE-GRA 已經穩定優於強 hand-crafted baseline。

### 最合理的下一步

接下來最值得做的是 `seg_01`：

- family: `0|1|15|2|3|4|5 @ gnb_1`
- time: `43.7s ~ 43.9s`
- 特點：gain 更大，但 test window 更短

如果 `seg_01` 也能重現 teacher，
就可以更有力地說明 P3.6g 的 supervision 結論不是只在單一家族成立。

## Seg_01 Focused Temporal Learner 結果

`seg_01` 也已經實際跑完。因為它只有 `3` 個 positive snapshots，
所以這次沒有只押單一切點，而是把兩個候選 split 都跑掉：

1. `split437`
   - train window end: `43.7s`
   - test window: `43.8s ~ 43.9s`
   - output: `p3_6i2_seg01_split437_temporal_learner/`
2. `split438`
   - train window end: `43.8s`
   - test window: `43.9s`
   - output: `p3_6i2_seg01_split438_temporal_learner/`

### Split 43.7 -> 43.8~43.9

split summary：

- background train scenarios: `150`
- focus train scenarios: `527`
- focus test scenarios: `2`
- focus train positive gain count: `7`
- focus test positive gain count: `2`

main comparison：

- No grouping: `0.5472`
- Offline teacher: `0.6043`
- Multi-feature: `0.6043`
- LE-GRA: `0.6043`

teacher imitation：

- Multi-feature: pairwise `1.0`, ARI `1.0`, NMI `1.0`
- LE-GRA: pairwise `1.0`, ARI `1.0`, NMI `1.0`

### Split 43.8 -> 43.9

split summary：

- background train scenarios: `150`
- focus train scenarios: `528`
- focus test scenarios: `1`
- focus train positive gain count: `8`
- focus test positive gain count: `1`

main comparison 也完全一致：

- No grouping: `0.5472`
- Offline teacher: `0.6043`
- Multi-feature: `0.6043`
- LE-GRA: `0.6043`

teacher imitation 也同樣是完美對齊：

- Multi-feature: pairwise `1.0`, ARI `1.0`, NMI `1.0`
- LE-GRA: pairwise `1.0`, ARI `1.0`, NMI `1.0`

### 解讀

`seg_01` 的價值比 `seg_02` 還高一點，因為它回答了兩個更嚴格的問題：

1. family 不再只是 `gnb_2` 上的 `0|1|2|3|4`
2. 即使是 `gnb_1` 上、含 cross-traffic `15` 的更大 family，
   LE-GRA 仍然可以完整重現 teacher

更重要的是，`seg_01` 的正增益本來就比 `seg_02` 更大：

- `seg_02` gain: `0.01190`
- `seg_01` gain: `0.05716`

而這一段仍然被 LE-GRA 完整吃下來。這讓目前的研究訊號變得更強：

> conservative redesign 後恢復的不只是「勉強可分」的 split regime，
> 而是包含較高增益、含 cross-traffic 干擾的 family；
> 只要 train/test supervision 對齊，LE-GRA 依然能精準重現 teacher。

### 目前最合理的總結

到目前為止，P3.6g、`seg_02`、`seg_01` 三輪結果合起來，已經能支持一個相當穩定的結論：

- train side 沒有正增益 split supervision 時，learner 會看起來像是「學不起來」
- 但一旦 supervision 對齊到真實存在的 split regime，
  LE-GRA 在多個 focused temporal slices 上都能完整重現 teacher

當然，這裡仍然有一個保守 caveat：

- Multi-feature 在這些 focused slices 上也一樣能完美追上 teacher

所以目前最精準的說法不是「LE-GRA 已經贏過強 baseline」，
而是：

> P3.6 的主要瓶頸已經不是 learner 在 coupled trace 上完全失效，
> 而是如何穩定找到、保留、並利用真正 informative 的 split-supervision regime。
