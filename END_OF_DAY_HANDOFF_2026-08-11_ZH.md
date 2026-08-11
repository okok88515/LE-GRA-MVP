# End-of-Day Handoff (2026-08-11)

這份文件是 2026-08-11 的最新研究與 repo 整理交接。

## 今天做完了什麼

今天的重點不是擴大新實驗，而是把 repo 與研究證據整理到「可以穩定接手」的狀態。

已完成：

1. 修正並 push 了昨天整理後的主線提交
2. 建立 repo artifact 管理規則
3. 把主線 showcase / control / focused subset 證據分層收進 git

## 今天新增並已 push 的 commits

1. `968a387`
   - `Add artifact hygiene guide and untracked triage`
2. `b3cb157`
   - `Add core r4/r8 showcase artifacts and radio coverage summaries`
3. `505faf5`
   - `Add focused subset and plateau control artifacts`

目前遠端 `origin/main` 已包含以上內容。

## 目前 repo 內的證據分層

### 1. 主線 showcase

- `p3_6r4_q10_history_conflict_bundle/`
- `p3_6r4_q10_history_conflict_spec.json`
- `p3_6r8_q10_temporal_decoy_flicker_bundle/`
- `p3_6r8_q10_temporal_decoy_flicker_spec.json`
- `p3_6q27_p35_radio_coverage.csv`
- `p3_6q27_q23_radio_coverage.csv`

定位：

- `r4`：
  - 目前 teacher 與 `resource-cost` gap 最大的 showcase
- `r8`：
  - 目前最具代表性的 hard-boundary benchmark
- `q27`：
  - radio-aware 路線的關鍵 coverage evidence

### 2. control / support

- `p3_6r2b_five_user_dualweak_plateau_bundle/`
- `p3_6r2b_five_user_dualweak_plateau_spec.json`
- `p3_6r2b_teacher_audit/`
- `p3_6r2c_five_user_dualweak_plateau_plus_bundle/`
- `p3_6r2c_five_user_dualweak_plateau_plus_spec.json`
- `p3_6r2c_teacher_audit/`

定位：

- 用來支撐 stable split-demand control
- 對主線有幫助，但不是第一主角

### 3. focused subset evidence

- `p3_6i2_focused_teacher_subset/`
- `p3_6q10_focused_teacher_subset/`

定位：

- 用來說明 full bundle 會稀釋真正 teacher-positive window
- 支撐為什麼 focused extraction 是必要的

## 今天新增的 repo 管理文件

- `REPO_ARTIFACT_GUIDE_ZH.md`
- `UNTRACKED_TRIAGE_2026-08-11_ZH.md`

用途：

- 前者規範哪些產物應該進 git、哪些只該留本機
- 後者把目前尚未追蹤的研究資產分級，避免之後又全部混在一起

## 目前還沒有收進 git 的東西

目前 `git status` 剩下的主要是 exploratory 支線：

- `r1 / r2 / r3 / r5 / r6`
- `r4` 的局部 decoy 變體

這些暫時沒有收，原因不是它們沒價值，而是：

1. 它們比較像 exploration trail
2. 目前主線敘事不需要一次把全部支線帶進 repo
3. 若未來要補 appendix，可以再挑代表性案例收

## 目前研究主線的最新表述

現在這個專案的主線不是：

- 「證明 LE-GRA 是最強通解」

而是：

- `CQI-only grouping` 太粗
- `resource-cost` 與 `multi-feature` 更接近真實 multicast grouping 問題
- `Offline teacher + exact DP` 是研究 backbone
- `LE-GRA` 保留為 exploratory / appendix line

## 如果下一個 agent 要接手，先做什麼

1. 先看 `git status`
2. 先讀：
   - `END_OF_DAY_HANDOFF_2026-08-11_ZH.md`
   - `SESSION_HANDOFF.md`
   - `REPO_ARTIFACT_GUIDE_ZH.md`
   - `UNTRACKED_TRIAGE_2026-08-11_ZH.md`
3. 先理解目前 repo 已經刻意分成：
   - main showcase
   - control support
   - focused subset evidence
4. 不要先把所有 exploratory bundle 全部 commit
5. 若要繼續整理 repo，優先只挑少量 appendix 級代表性案例

## 建議的下一步

最合理的下一步有兩條：

1. repo/報告整理線
   - 挑少量 appendix 等級 failure cases 收進 repo
   - 補強 handoff / report 對 `r4 / r8 / r2c` 的敘述

2. 研究延伸線
   - 從 `resource-cost / multi-feature` 主線出發
   - 繼續設計更能放大主線差距的 regime
   - 但不要一開始就回去做大規模 LE-GRA learner-side tweak sweep
