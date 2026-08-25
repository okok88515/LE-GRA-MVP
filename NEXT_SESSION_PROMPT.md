# Prompt for the next Codex session

把下面這段直接貼給下一個 Codex 使用：

```text
請在 LE-GRA-MVP 專案延續 2026-08-26 的 real Simu5G conditional-gating
研究。先不要改 utility、features、K、allocator 或 gate threshold。

開始前：
1. 執行 `git status`，不要提交三個 legacy mobility CSV 的 Windows
   line-ending 假修改。
2. 完整閱讀 `SESSION_HANDOFF.md` 最上方的 2026-08-26 authoritative
   section。
3. 閱讀 `REAL_SIMU5G_CONDITIONAL_GATING.md`、
   `REAL_SIMU5G_TEMPORAL_REGIME_ANALYSIS.md`、`REAL_SIMU5G_MULTISEED.md`。
4. 用中文先摘要目前結論，再開始修改或執行。

目前已完成：
- 真實 Simu5G 10 seeds × low/mid/high，每 run 15 snapshots。
- method-owned previous_quality 的 closed-loop evaluation。
- CQI、CQI+cost 2-way、always-on switching 3-way 比較。
- switching source attribution、regime tree、path-erosion analysis。
- conditional margin gate 與 seed-level LOSO threshold selection。
- eta=0 精確重現 3-way，eta=infinity 精確重現 2-way。

核心結果：
- CQI+cost 是穩健 core；switching 是少量 conditional refinement。
- LOSO gated 在 mid/high pooled utility 相對 2-way 為 +0.001301，
  95% CI [+0.000542,+0.002176]，seed W/T/L 9/1/0。
- 相對 CQI 為 +0.024411，CI [+0.020382,+0.028432]，10/0/0。
- 相對 always-on 3-way 為 +0.000060，CI 跨 0，尚未證明 gating
  整體顯著優於 always-on。
- 9/10 folds 選 eta=.020；seed_0006 fold 以極小差距選 .005，仍發生
  mid/light path trap。

下一步是 confirmatory data，不是繼續調門檻：
- 事先凍結 eta=.020。
- 生 seed_0011..seed_0030，共 20 個新 seeds。
- 每 seed 跑 low/mid/high，共 60 個 Simu5G runs；三種 load 是從同一
  trace 後處理，不是額外 simulator runs。
- 預估 raw generation 32–36 分鐘，完整 QA+分析約 45–50 分鐘，抓一小時。
- 新 20 seeds 必須保留為 confirmatory test set，不可再拿來調 eta。

先做必要 plumbing：
- 讓 `validate_real_simu5g_multiseed.py` 和 temporal confirmatory runner
  接受明確 seed range，而非寫死 1..10。
- 固定 gate eta=.020，只跑 CQI、2-way、always-on 3-way、fixed-gated。
- 不要先跑七個 eta sweep，也不要用新 seeds 重選 eta。

raw batch command：
`python .\run_real_simu5g_multiseed.py --seeds 11-30`

批次預設輸出在 WSL：
`/home/opp_env/p3_5_workspace/p3_7_multiseed_v3_outputs`
批次可續跑，不會覆寫完成 runs。

完成後主要判準：
1. confirmatory mid/high pooled gated-vs-2way 的 seed-level paired CI > 0。
2. high/light、high/medium 增益重現。
3. mid/light 不再出現系統性負向結果。
4. fixed gate 明確打敗 CQI。
5. 分開報告原 10 seeds exploratory 與新 20 seeds confirmatory，最後才
   可另報 combined 30-seed sensitivity analysis。

fixed-gate confirmation 完成後，三條長期研究方向都要保留並依序探索；
詳細 protocol 在 `POST_CQI_RESEARCH_ROADMAP_ZH.md`：
1. 同 CQI、不同頻率選擇性：完整 RB profile、pairwise overlap/regret
   graph、spectral/correlation/graph partitioning，並和 full-profile
   k-means 做同輸入公平比較。
2. 同 CQI、不同 QoE switching state：學習或近似 pairwise same-group
   utility regret，而不是只把 previous_quality 當 joint k-means 座標。
3. 短期趨勢：顯式 slope/volatility/outage/forecast，並把 teacher 改為
   future-H cumulative utility；真實 future 只能當 oracle ceiling。

三條先各自做 ablation，最後才整合成 dynamic compatibility graph。
不要把 seeds 11..30 同時宣稱為 fixed-gate 與未來新方法的 untouched
confirmatory set；看過後若用於新方法，只能算 exploratory/nested-CV。
```
