# Untracked Triage (2026-08-11)

這份清單記錄在加入新的 `.gitignore` 後，repo 內仍然存在的主要未追蹤研究資產，以及目前建議的處理方式。

## 建議優先保留並考慮 commit 的主線資產

- `p3_6r4_q10_history_conflict_bundle/`
- `p3_6r4_q10_history_conflict_spec.json`
- `p3_6r4_teacher_audit/`
- `p3_6r8_q10_temporal_decoy_flicker_bundle/`
- `p3_6r8_q10_temporal_decoy_flicker_spec.json`
- `p3_6q27_p35_radio_coverage.csv`
- `p3_6q27_q23_radio_coverage.csv`

原因：

- `r4` 是目前 teacher 與 `resource-cost` gap 最大的 showcase
- `r8` 是目前最有代表性的 hard-boundary benchmark
- `q27` coverage csv 是 radio-aware 主線的重要 evidence

## 建議保留，但不是第一優先 commit 的 supporting assets

- `p3_6i2_focused_teacher_subset/`
- `p3_6q10_focused_teacher_subset/`
- `p3_6r2c_five_user_dualweak_plateau_plus_bundle/`
- `p3_6r2c_five_user_dualweak_plateau_plus_spec.json`
- `p3_6r2c_teacher_audit/`
- `p3_6r2b_five_user_dualweak_plateau_bundle/`
- `p3_6r2b_five_user_dualweak_plateau_spec.json`
- `p3_6r2b_teacher_audit/`

原因：

- 這些是很好的 control / intermediate evidence
- 但相較 `r4` / `r8`，它們不是目前最強的敘事主角

## 建議暫時不要 commit 的 exploratory variants

- `p3_6r1_four_user_dualweak_crossover_bundle/`
- `p3_6r1_four_user_dualweak_crossover_spec.json`
- `p3_6r1_teacher_audit/`
- `p3_6r2_five_user_dualweak_decoy_bundle/`
- `p3_6r2_five_user_dualweak_decoy_spec.json`
- `p3_6r2_teacher_audit/`
- `p3_6r3_q10_dual_flip_corridor_bundle/`
- `p3_6r3_q10_dual_flip_corridor_spec.json`
- `p3_6r3_teacher_audit/`
- `p3_6r4b_q10_history_conflict_balanced_bundle/`
- `p3_6r4b_q10_history_conflict_balanced_spec.json`
- `p3_6r4c_q10_boundary_flip_bundle/`
- `p3_6r4c_q10_boundary_flip_spec.json`
- `p3_6r5_n3_dualweak_history_conflict_bundle/`
- `p3_6r5_n3_dualweak_history_conflict_spec.json`
- `p3_6r5c_n3_early_dualweak_pair_bundle/`
- `p3_6r5c_n3_early_dualweak_pair_spec.json`
- `p3_6r6_e3_dualweak_pair_bundle/`
- `p3_6r6_e3_dualweak_pair_spec.json`

原因：

- 這些比較像探索過程中的支線證據
- 若之後要補 appendix 或 method-failure chronology，可以再挑代表性版本 commit

## 建議暫時不要 commit 的 `r4` 局部分支變體

- `p3_6r4_q10_history_conflict_bundle_d1_ue4_decoy_mild_bundle/`
- `p3_6r4_q10_history_conflict_bundle_d2_ue4_decoy_medium_bundle/`
- `p3_6r4_q10_history_conflict_bundle_d3_ue5_decoy_mild_bundle/`
- `p3_6r4_q10_history_conflict_bundle_d4_dual_decoy_mild_bundle/`
- `p3_6r4_q10_history_conflict_bundle_d5_tighter_ue6_mild_ue4_bundle/`
- `p3_6r4_q10_history_conflict_bundle_d6_weaker_ue2_stronger_decoy_bundle/`

原因：

- 這些是 `r4` plateau 周邊的局部探索
- 現階段敘事只需要知道「有做過、但沒有打破 plateau」
- 不需要把每個局部 bundle 都帶進主線 repo

## 建議下一步

1. 若今天要做一次乾淨 commit：
   - 先只處理 `.gitignore`
   - `REPO_ARTIFACT_GUIDE_ZH.md`
   - `UNTRACKED_TRIAGE_2026-08-11_ZH.md`
   - `SESSION_HANDOFF.md`
2. 下一輪若要補主線研究資產：
   - 優先挑 `r4`、`r8`、`q27 coverage`
3. 若未來 repo 還是太大：
   - 再把 exploratory bundles 移到外部 archive 或 release-style artifact 管理
