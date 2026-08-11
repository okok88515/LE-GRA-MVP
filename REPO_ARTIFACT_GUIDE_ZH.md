# Repo Artifact Guide

最後更新：2026-08-11

這份文件用來規範 `LE-GRA-MVP` repo 中哪些產物應該進 git，哪些只應該留在本機。

## 核心原則

1. `可重建的暫存` 不進 git。
2. `研究主線需要引用的關鍵 bundle / audit / report` 才進 git。
3. `大量自動搜尋產物` 只保留：
   - 產生它們的 script
   - leaderboard / summary / spec template
   - 必要時少數代表性案例
4. 如果某個資料夾很大、很多個、名字帶有編號掃描痕跡，預設先不要 commit。

## 應該進 git 的內容

- 研究敘事與交接文件：
  - `SESSION_HANDOFF.md`
  - `END_OF_DAY_HANDOFF_*.md`
  - `project_overview*.html`
  - `report_conclusion_zh.html`
  - `roadmap_todo.html`
  - 各階段 `P*_ZH.md`
- 可重現實驗的程式與規格：
  - `build_*.py`
  - `run_*.py`
  - `search_*.py`
  - `mine_*.py`
  - `*_spec.json`
- 關鍵研究資產：
  - 主線 bundle
  - 主線 teacher audit
  - 主線 focused learner result
  - 小型但會在報告中引用的 summary / matrix / leaderboard

## 不應該進 git 的內容

- `_tmp_*`
  - 暫存 probe
  - debug csv
  - 臨時 shell 包裝
- 大量 sweep / mining 的原始輸出資料夾：
  - `family_corridor_batch_runs_*`
  - `family_corridor_mining_global*`
  - `n3_dualweak_variant_search/`
  - `q10_decoy_collision_search/`
  - `q10_history_conflict_variant_search/`
  - `r8_boundary_variant_search/`
  - `source_family_candidates_latest/`
- 大量自動生成的 bundle family：
  - `p3_6r5s_*_bundle/`
  - `p3_6r7_*_bundle/`
  - `p3_6r8s_*_bundle/`
- 診斷 sidecar：
  - `raw_radio_diag.csv`

## 遇到新產物時怎麼判斷

如果一個產物符合以下任兩項，預設先不要 commit：

- 可以由現有 script 重跑得到
- 是 sweep / search 的中間輸出
- 數量很多
- 檔案很大
- 不會直接出現在報告或 handoff 中

如果一個產物符合以下任兩項，通常值得 commit：

- 會在報告或 handoff 被直接引用
- 是目前最佳 showcase regime
- 是後續 agent 需要直接讀取的關鍵 evidence
- 重跑成本高，而且已經確認是主線研究資產

## 目前建議保留策略

- `r4`：
  - 保留，因為它是目前 teacher 與 `resource-cost` gap 最大的 showcase
- `r8`：
  - 保留，因為它是新的 hard-boundary benchmark
- `q10` / `q23`：
  - 保留，因為它們分別代表已成功家族與 onset-failure benchmark
- `r5s` / `r7` / `r8s` 大批自動變體：
  - 不要全進 git
  - 只保留 script、leaderboard、必要 spec

## 今天這次整理做了什麼

已把下列類型加入 `.gitignore`：

- `_tmp_*`
- `family_corridor_batch_runs_*`
- `family_corridor_mining_global*`
- `n3_dualweak_variant_search/`
- `q10_decoy_collision_search/`
- `q10_history_conflict_variant_search/`
- `r8_boundary_variant_search/`
- `source_family_candidates_latest/`
- `p3_6r5s_*_bundle/`
- `p3_6r7_*_bundle/`
- `p3_6r8s_*_bundle/`

## 建議下一步

1. 重新看一次 `git status`
2. 確認工作樹只剩真正值得處理的檔案
3. 若還有少量未追蹤資料夾，再逐一判斷它們是：
   - 主線研究資產
   - 還是應該再補 ignore 規則
