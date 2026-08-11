# Prompt for the next Codex session

把下面這段直接貼給下一個 Codex / Claude 使用：

```text
請先完整閱讀這個 LE-GRA-MVP 專案的最新研究交接，不要一開始就擴大實驗，也不要先把 exploratory 變體全部收進 repo。

閱讀順序：
1. END_OF_DAY_HANDOFF_2026-08-11_ZH.md
2. SESSION_HANDOFF.md
3. REPO_ARTIFACT_GUIDE_ZH.md
4. UNTRACKED_TRIAGE_2026-08-11_ZH.md
5. project_overview_zh.html
6. report_conclusion_zh.html
7. roadmap_todo.html
8. project_overview.html

開始前先做：
1. 先看 `git status`
2. 用一句話總結目前研究主線
3. 確認目前 repo 的主線敘事已改成：
   - `resource-cost / multi-feature` 是主角
   - `Offline teacher + exact DP` 是 backbone
   - `LE-GRA` 是 exploratory / appendix line

目前研究主線：
- 不再把問題寫成「證明 LE-GRA 是通用最佳方法」
- 現在主線是：
  - `CQI-only grouping` 太粗
  - `resource-cost` 與 `multi-feature` 更接近真實 multicast grouping 問題
  - 研究價值在於建立 feature-rich grouping pipeline 與 teacher-aligned evaluation

目前 repo 已經整理成三層證據：

1. 主線 showcase
   - `r4`
   - `r8`
   - `q27 radio coverage`

2. control / support
   - `r2b`
   - `r2c`

3. focused subset evidence
   - `p3_6i2_focused_teacher_subset`
   - `p3_6q10_focused_teacher_subset`

目前已經進 git 並 push 的最新 commits：
- `968a387` Add artifact hygiene guide and untracked triage
- `b3cb157` Add core r4/r8 showcase artifacts and radio coverage summaries
- `505faf5` Add focused subset and plateau control artifacts

目前最重要的研究判斷：
1. LE-GRA 不是通解
2. LE-GRA 也不是目前最穩定、最值得主推的唯一方法
3. `resource-cost` 與 `multi-feature` 更適合當主線敘事
4. LE-GRA 的價值仍在：
   - 幫助辨識困難 regime
   - 幫助分析 learner failure mode
   - 幫助界定 localized candidate generation 的價值

現在不要優先做的事：
- 不要先擴大 matrix / seeds / Kmax
- 不要先回去做 learner-side 微調 sweep
- 不要先把所有 exploratory bundles 都 commit
- 不要先重寫整個方法線

目前 repo 管理規則：
- 先讀 `REPO_ARTIFACT_GUIDE_ZH.md`
- `_tmp_*`、大批自動搜尋輸出、可重建 sweep 結果不要直接 commit
- 若要收新資產，優先只收：
  - 會出現在報告中的主線證據
  - 最佳 showcase regime
  - 高價值 control regime

目前還留在本機、尚未進 git 的主要 exploratory 資產：
- `r1 / r2 / r3 / r5 / r6`
- `r4` 的局部 decoy 變體

下一步建議優先順序：
1. 先判斷剩下的 untracked exploratory 資產中，是否有少數代表性 failure/control 值得保留
2. 若要補 repo，優先挑 appendix 等級的代表性案例，而不是全收
3. 若要補報告，優先整理：
   - `r4` 為什麼是最大 gap showcase
   - `r8` 為什麼是 hard-boundary benchmark
   - `r2c` 為什麼是 stable split-demand control
4. 若要繼續研究，優先從 feature-centric / resource-aware 角度出發，而不是先把 LE-GRA 擴成大矩陣

回答請以中文為主，先講清楚你目前理解的研究脈絡、repo 現況、未完成項，再開始做事。
```
