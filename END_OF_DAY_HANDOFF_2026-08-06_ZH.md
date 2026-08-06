# End-of-Day Handoff (2026-08-06)

## 先看這幾個檔

回家後建議閱讀順序：

1. `SESSION_HANDOFF.md`
2. `P3_6M_2_POSITIVE_FAMILY_DECOY_ZH.md`
3. `P3_6M_3_FOCUSED_LEARNER_ZH.md`
4. `P3_6M_4_SLICE_REPLICATION_ZH.md`

## 今天做到哪裡

今天已經完成 `P3.6m-2`、`P3.6m-3`、`P3.6m-4`。

### P3.6m-2

從本來就有正增益 split 的 family：

- `0|1|15|2|3|4|5 @ gnb_1`

出發，把 `ue 4` 注入成 decoy weak candidate。

關鍵結果：

- `43.7s ~ 43.9s`
- teacher split 從原本只 isolate `ue 15`
- 變成弱組 `{ue 15, ue 4}`
- 但仍然保持正增益

### P3.6m-3

對這條新 regime 跑 focused learner / ablation。

結果第一次出現：

- `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`

而且差距不是因為有沒有 split，而是因為：

- teacher 會把 `{ue15, ue4}` 放進弱組
- LE-GRA / multi-feature 還是只 isolate `ue15`

### P3.6m-4

先做 decoy-only sweep，結果證明：

- 光調 `ue4 decoy` 不會把 regime 往前推
- threshold 還是在 `ue15`

接著做 `P3.6m-4b`：

- 只對 `43.6s` 的 `ue15` 做 threshold nudge

結果：

- 正增益 segment 從 `43.7s~43.9s`
- 擴成 `43.6s~43.9s`

但要注意：

- `43.6s` 還是舊的單弱者 split
- 真正 dual-weak `{ue15, ue4}` 的 regime 還是 `43.7s~43.9s`

## 目前最重要的結論

現在最強的證據已經不是「LE-GRA 能不能 split」。

而是：

- teacher 會把 `{ue15, ue4}` 一起視為弱組
- LE-GRA / multi-feature 還學不會這個 secondary weak candidate

也就是說，當前 bottleneck 已經很清楚：

- learner 不是不會分群
- learner 是還不會把 decoy weak user 也拉進去

## 回家後最建議做的下一步

直接進 `P3.6m-5`。

方向：

- 做 learner-side supervision redesign
- 目標不是再擴 `43.5`
- 而是讓 LE-GRA 真正學會 `{ue15, ue4}` 這種 dual-weak split identity

## 目前最值得當主評估 slice 的區段

主 slice：

- `43.7s ~ 43.9s`
- family: `0|1|15|2|3|4|5 @ gnb_1`

輔助 bridge slice：

- `43.6s`
- 這格有正增益，但還不是 dual-weak split

## 相關輸出資料夾

最重要的資料夾：

- `p3_6m2_positive_family_decoy_bundle/`
- `p3_6m2_teacher_audit/`
- `p3_6m2_seg01_split437_temporal_learner/`
- `p3_6m4b_threshold_nudge_bundle/`
- `p3_6m4b_teacher_audit/`
- `p3_6m4b_seg01_split436_temporal_learner/`

## 如果你要直接開新一輪工作

最直接的起手式是：

1. 先重讀 `P3_6M_4_SLICE_REPLICATION_ZH.md`
2. 把 `43.7~43.9` 當主 regime
3. 開始設計 `P3.6m-5` 的 supervision redesign

## 一句話總結

今天最大的進展是：我們終於找到一條「teacher 有正增益、而且 teacher split identity 和 LE-GRA / multi-feature 真的不同」的 regime，而且現在已經有 3 個連續 dual-weak snapshot 可以支撐這個結論。
