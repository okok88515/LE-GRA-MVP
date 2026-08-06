# Prompt for the next Codex session

把下面整段直接貼給明天公司的 Codex：

```text
請先完整閱讀這個 LE-GRA-MVP 專案的最新研究交接，不要一開始就擴大實驗，也不要先重做已經證明無效的小 tweak。

閱讀順序：
1. END_OF_DAY_HANDOFF_2026-08-06_ZH.md
2. SESSION_HANDOFF.md
3. P3_6M_19_BOUNDARY_SUPPORT_WEIGHTING_ZH.md
4. P3_6M_20_BOUNDARY_WEIGHTING_ROBUSTNESS_ZH.md
5. P3_6M_21_M4B_BOUNDARY_TRANSFER_CHECK_ZH.md
6. P3_6M_22_CANDIDATE_CONDITIONED_WEAK_GROUP_V1_ZH.md
7. P3_6M_23_CANDIDATE_CONDITIONED_CALIBRATION_ZH.md
8. P3_6M_24_BOUNDARY_AWARE_PAIR_CONSTRUCTION_V1_ZH.md
9. run_p3_6g_temporal_learner.py
10. run_p3_6_coupled_learner.py
11. le_gra_mvp.py

目前研究狀態重點：
- 主研究 family 仍然是 `0|1|15|2|3|4|5 @ gnb_1`
- 目前真正困難的 dual-weak regime 仍然是 `p3_6m4b_threshold_nudge_bundle/bundle`
  上的 `43.7s ~ 43.9s`
- teacher 的關鍵 weak group 是 `{ue15, ue4}`
- learner / multi-feature / CQI 仍然卡在舊的 `ue15-only` 解

目前最重要結論：
1. `P3.6m-17` 已證明 normalized-support selector 修正有效
2. `P3.6m-19 ~ P3.6m-20` 已證明 minimal boundary-aware replay 在 `m2` 上是真的有效，且通過第一輪 robustness check
3. 但 `P3.6m-21` 已證明 replay-only 無法 transfer 到 `m4b`
4. `P3.6m-22 ~ P3.6m-23` 已證明 candidate-membership-BCE-only 即使做最小 calibration，也完全推不動 `m4b`
5. `P3.6m-24` 已證明最小版 boundary-aware pair construction 也仍然推不動 `m4b`

所以現在的停損點很清楚：
- 不要再做 replay-only sweep
- 不要再做 candidate BCE 權重微調
- 不要再做單點 pair-priority 小修
- 不要回頭做 selector/tie-break 類微調

現在最值得做的下一步只有一條主線：
- 做「最小聯合版 supervision」

具體目標：
- 把已經各自存在但單獨都不夠的三個 hook 組合起來：
  1. boundary-aware replay
  2. candidate-conditioned weak-group supervision
  3. boundary-aware pair construction

工作原則：
- 先看 git status
- 先理解現有實作，不要重做已經證明失敗的 isolated tweak
- 先做最小聯合版，不要擴大 seeds / Kmax / matrix
- 每做一步都更新 SESSION_HANDOFF.md
- 如果跑實驗，優先只在 `m4b` 主 regime 做 focused validation

建議第一步：
1. 檢查目前 repo 狀態
2. 讀完上述文件
3. 用一句話總結目前 bottleneck
4. 直接實作最小聯合版 supervision
5. 在 `p3_6m4b_threshold_nudge_bundle/bundle` 上做 focused test：
   - train end = `43.6`
   - test = `43.7 ~ 43.9`
   - 先不要擴大矩陣

如果最小聯合版還是完全不動，再明確總結：
- 目前 minimal learner-side local tweaks on `m4b` are insufficient
- 下一步就應該轉向更強的 localized hard negatives / structure-level redesign

回答請以中文為主，先講清楚脈絡與判斷，再開始做事。
```
