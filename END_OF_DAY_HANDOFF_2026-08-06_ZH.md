# End-of-Day Handoff (2026-08-06)

這份文件是給明天在公司電腦接續研究時用的快速交接版。

如果只看一份短文件，先看這份；如果要完整脈絡，再看 `SESSION_HANDOFF.md`。

## 明天最先讀什麼

建議閱讀順序：

1. `END_OF_DAY_HANDOFF_2026-08-06_ZH.md`
2. `SESSION_HANDOFF.md`
3. `P3_6M_19_BOUNDARY_SUPPORT_WEIGHTING_ZH.md`
4. `P3_6M_20_BOUNDARY_WEIGHTING_ROBUSTNESS_ZH.md`
5. `P3_6M_21_M4B_BOUNDARY_TRANSFER_CHECK_ZH.md`
6. `P3_6M_22_CANDIDATE_CONDITIONED_WEAK_GROUP_V1_ZH.md`
7. `P3_6M_23_CANDIDATE_CONDITIONED_CALIBRATION_ZH.md`
8. `P3_6M_24_BOUNDARY_AWARE_PAIR_CONSTRUCTION_V1_ZH.md`

## 目前研究主軸在哪裡

目前真正的主線已經不是一般 matrix，也不是 P3.5 coupled bring-up，而是：

- `P3.6m`
- 以同一個 family 做 focused learner diagnosis

核心 family：

- `0|1|15|2|3|4|5 @ gnb_1`

目前最重要的 bundle / regime：

- `p3_6m4b_threshold_nudge_bundle/bundle`
- main dual-weak evaluation window：`43.7s ~ 43.9s`

這個 regime 的真正關鍵不是「會不會 split」，而是：

- teacher 會學到 dual-weak `{ue15, ue4}`
- learner / multi-feature / CQI 會退回 `ue15-only`

## 今天之前已經確立的結論

### 1. normalized-support selector 修正是有效的

`P3.6m-17` 已證明：

- 之前 restart selector 的一個大問題，是 support scoring 跟 training-time normalization 不一致
- 修正之後，support-side selector 在對的 slice 上是有辨識力的

這代表：

- selector 本身不是完全沒訊號
- 至少在部分 regime 上，candidate 選擇是能被修好的

### 2. minimal boundary-aware replay 在 `m2` 上是真的有效

`P3.6m-19` 到 `P3.6m-20` 已證明：

- 在 `p3_6m2_positive_family_decoy_bundle/bundle`
- minimal boundary-aware support replay 不是假訊號
- 它不只會改 selector
- 還會真的把 LE-GRA 往 teacher 推

而且 robustness check 已經成立：

- `boundary_support_start = 43.3 / 43.4 / 43.5` 都可以
- `43.8 only`、`43.9 only` 也都可以

所以 `m2` 上的 replay 成功是可靠結論。

### 3. replay-only 無法 transfer 到 `m4b`

`P3.6m-21` 是一個很重要的停損點。

同樣的 minimal replay protocol 搬到 `m4b` 後：

- support-side imitation 仍然完美
- replay 也確實有吃進去
- 但 holdout 完全沒動

所以現在不能再把問題理解成：

- 只是 boundary support 不夠重

### 4. candidate-membership-BCE-only 也推不動 `m4b`

`P3.6m-22` 先實作了最小版 candidate-conditioned weak-group supervision。

方向是：

- 在 teacher hardest group 裡
- 對 top-2 resource-cost users 加 sparse candidate membership BCE

但第一版沒動。

接著 `P3.6m-23` 做了最小 calibration：

- 掃 `candidate_membership_weight`
- 掃 `candidate_secondary_scale`

四組結果全部完全一樣，沒有任何門檻反應。

所以：

- 問題不是係數太小
- `candidate BCE-only` 這條小 tweak 路線，可以先停損

### 5. 最小版 boundary-aware pair construction 也推不動 `m4b`

`P3.6m-24` 又往前做了一步：

- 在 pair weighting 層，直接把 supervision 壓到
  - primary weak ↔ secondary weak 正 pair
  - secondary weak ↔ hardest-group 外部成員負 pair
  - primary weak ↔ hardest-group 外部成員負 pair

但結果仍然沒動：

- `teacher > LE-GRA = CQI`
- support-side 還是 `1.0`

所以現在可以更有把握地說：

- `m4b` 的 bottleneck 已經不是一個 isolated minimal tweak 能打開的

## 今天做完後的總結判斷

如果只看 `m4b`，現在的 stop-loss 已經很清楚。

已經試過、而且可以先停的東西：

- replay-only sweep
- candidate BCE 權重微調
- pair-priority 小修
- selector / tie-break 類微調

這些方向現在再做，資訊增益會很低。

## 明天最值得做的唯一主線

明天如果要接著做，最合理的不是再做一個新的 isolated tweak，而是：

- 做「最小聯合版 supervision」

也就是把現在已經存在、但單獨都不夠的三個 hook 組起來：

1. boundary-aware replay
2. candidate-conditioned weak-group supervision
3. boundary-aware pair construction

目標不是擴大實驗，而是回答一個很明確的問題：

- 這三個最小 learner-side hooks 聯合起來，能不能把 `m4b` 稍微推離 plateau？

## 明天不建議做的事

先不要做：

- 擴 Kmax
- 擴 seeds
- 擴 matrix
- 回頭做更多 replay-only sweep
- 繼續做 candidate BCE 的權重微調
- 再做單一 pair-priority 小 tweak

也就是說：

- 先不要把時間花在已經證明「單獨不夠」的支線上

## 明天開工建議順序

1. `git pull`
2. `git status`
3. 先讀這份文件與 `SESSION_HANDOFF.md`
4. 確認目前主 regime 還是：
   - bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
   - train end: `43.6`
   - test: `43.7 ~ 43.9`
5. 直接做最小聯合版 supervision
6. 只在 `m4b` 上做 focused test
7. 更新 `SESSION_HANDOFF.md`

## 目前最重要的實驗輸出

建議明天若要追數據，優先看這幾個目錄：

- `p3_6m19b_m2_boundary_weighting_r16/`
- `p3_6m20_m2_boundary_start_434_r16/`
- `p3_6m20_m2_holdout_438_only_r16/`
- `p3_6m20_m2_holdout_439_only_r16/`
- `p3_6m21_m4b_boundary_weighting_transfer_r16/`
- `p3_6m22_m4b_candidate_conditioned_v1/`
- `p3_6m23_m4b_candidate_calib_w4_s4/`
- `p3_6m24_m4b_candidate_boundary_pairs_v1/`

## 一句話版本

今天最重要的結論是：

- `m2` 已經證明 minimal replay 真的有效
- 但 `m4b` 仍然卡住，而且 isolated learner-side minimal tweaks 都推不動
- 明天應該直接做「最小聯合版 supervision」，而不是回頭做更多單點微調
