# Prompt for the next Codex session

將下列內容直接貼給公司電腦的 Codex：

```text
請先完整閱讀這個 LE-GRA-MVP 專案的最新研究交接，不要一開始就擴大實驗或改 learner。

閱讀順序：
1. SESSION_HANDOFF.md
2. P3_5_SUMO_SIMU5G_COUPLING_ZH.md
3. P3_6_NEXT_STEPS_ZH.md
4. P3_4_SIMU5G_RADIO_EXPORTER_ZH.md
5. SIMU5G_RADIO_SCHEMA.md
6. SUMO_MOBILITY_SCHEMA.md
7. p3_5_coupled_bundle/radio/export_metadata.json
8. p3_5_coupled_bundle/bundle/scenarios.csv
9. p3_5_coupled_bundle/bundle/users.csv
10. build_p3_5_coupled_bundle.py
11. run_p3_5_coupled_test.py
12. simu5g_raw_radio_export.py
13. medium_matrix_results_v2_after_grad_fix/main_comparison_matrix.csv
14. medium_matrix_results_v2_after_grad_fix/feature_ablation.csv
15. medium_matrix_results_v2_after_grad_fix/teacher_imitation_diagnostics.csv

目前 Git 主線的重要進度：
- P0–P2.6 learner-focused studies 已完成；gradient fix、resource-cost feature、teacher
  strength 等結論仍成立。
- P3.0 trace schema、P3.1 SUMO mobility adapter、P3.2 radio join 已完成。
- P3.3 真實 Simu5G 環境已完成。
- P3.4 已用 Simu5G NR AMC 匯出真實 per-UE/per-band CQI 與 TBS。
- P3.5 已完成同一 simulation clock 的 SUMO+Veins+Simu5G coupled run、stable
  SUMO ID mapping、25-band completeness、P3.2 join 和 offline teacher execution。

P3.5 acceptance evidence：
- 2 個 SUMO vehicles；stable mapping 為：
  `0 -> Highway.car[0] -> Simu5G 2049`
  `1 -> Highway.car[1] -> Simu5G 2050`
- 67 mobility rows、27,950 raw radio rows。
- 67 normalized radio user rows、1,675 radio RB rows。
- CQI warm-up 後有 55 scenarios、59 users、1,475 RB rows。
- Offline teacher 55/55 scenarios 通過。
- `python -u .\run_p3_5_coupled_test.py` 已通過。

重要限制：這份 P3.5 trace 是 integration artifact，不是訓練資料。它只有兩台車、
CQI 全為 15，而且 previous_quality=3 是明確標示的 experiment control，不是實測
video state。因此不要用這份 trace 跑 learner ranking，也不要擴大 Kmax/seeds。

你的任務是進入 P3.6：
1. 先檢查 git status 與最新 commit，確認 pull 完整。
2. 先執行 `python -u .\run_p3_5_coupled_test.py`；如果公司電腦沒有 simulator
   runtime，先讀 p3_5_install_environment.sh，不要假設 WSL distro 已存在。
3. 優先實作 `audit_coupled_trace.py`，量化目前 coupled trace 的 active UE、CQI
   saturation、per-band TBS dispersion、ambiguous-pair ratio、handover、resource
   pressure、quality distribution 與 join exclusions。
4. 用目前 P3.5 trace 建立 baseline audit，應明確顯示 CQI saturation 問題。
5. 再提出並實作一個最小 informative coupled scenario 改進；一次只改一組因素，
   例如 duration/vehicle density、gNB-route geometry、interference 或 handover。
6. 重新跑 audit，證明資料比 P3.5 smoke trace 更有研究資訊。
7. 接著定位並設計真實 video application quality recorder；不允許 random/fixed
   imputation，也不能直接由 CQI 推回 previous quality。
8. 所有修改都要保留 stable module-path ID mapping、同一 simulation timestamp、
   完整 per-band counterfactual TBS，並讓 P3.2 join與 offline teacher 繼續通過。

除非資料 audit 先證明值得，否則不要擴大 Kmax、seeds、duration 或整體 learner
matrix。回答與報告以繁體中文為主，先整理你讀到的研究脈絡與 P3.6 計畫，再動手。
```

## 公司電腦環境提醒

Git 會帶走程式、patch、raw evidence 與 bundle，但不會帶走 WSL/Nix simulator
installation。公司電腦若沒有 `LE-GRA-opp-env`，需先依 P3.3/P3.5 腳本建立環境。
執行腳本時，將範例中的 `/c/Users/User/Documents/LE-GRA-MVP` 換成公司電腦專案的
實際 WSL mount path。
