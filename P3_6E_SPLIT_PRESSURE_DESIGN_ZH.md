# P3.6e Split-Pressure Coupled Scenario Design

更新日期：2026-08-06

## 為什麼要做 P3.6e

P3.6d teacher-decision audit 已經把問題講得非常清楚：

- full bundle `614` 個 snapshots 中，offline teacher 只有 `1` 個 snapshot 回傳多群組
- 但那個案例相對單群組的 utility gain 只有 `1.11e-16`
- learner test split `311` 個 snapshots 中，`0` 個多群組

所以現在不是 learner 先不夠強，而是 coupled trace 還停在：

- `single-group trivial regime`

P3.6e 的任務，就是把 coupled trace 推進到：

- `teacher sometimes prefers split grouping`

也就是讓 offline teacher 不再幾乎永遠回傳單群組，真正產生可學的 supervision diversity。

## P3.6e 的核心理念

P3.6a 已經把資料從「完全沒資訊」推到「有 CQI variation、handover、quality state」。
但 P3.6d 證明，這些變化還沒有轉成真正的 grouping decision pressure。

因此 P3.6e 不再只是追求「更多變化」，而是要刻意製造三種會影響 grouping 的壓力：

1. `resource-pressure`
   讓 RB 預算更緊，單群組不一定同時照顧到所有人的 QoE。

2. `resource-cost heterogeneity`
   讓同一時刻的 UE 在 per-band rate / resource cost 上真的有差，而不是都差不多。

3. `QoE-state heterogeneity`
   讓 previous quality / switching penalty 在群內不一致，拆群才有機會帶來 utility 改善。

一句話講：

> P3.6e 不是再把 trace 做得更「熱鬧」，而是要把 trace 做到 teacher 對 split / merge 真的有偏好差異。

## 設計原則

### 1. 不覆寫 P3.6 baseline

保留現有：

- `p3_6_coupled_scenario/`
- `p3_6_coupled_output/`
- `p3_6_coupled_bundle/`
- `p3_6_teacher_audit/`

P3.6e 應該建立新的平行資產：

- `p3_6e_coupled_scenario/`
- `p3_6e_coupled_output/`
- `p3_6e_coupled_bundle/`
- `p3_6e_teacher_audit/`
- `build_p3_6e_coupled_bundle.py`
- `p3_6e_run_split_pressure_coupled.sh`

這樣比較才乾淨。

### 2. 先改資料 regime，再碰 learner

P3.6e 的成功標準不是 learner 分數，而是：

- offline teacher 是否開始穩定地出現 `group_count > 1`
- 這些多群組決策是否相對單群組真的有正 utility gain

### 3. 一次只加「會影響 grouping」的壓力

避免同時亂加太多因素。P3.6e 的設計要能回答：

- 是 overlap 太少？
- 是 budget 不夠緊？
- 是 UE profile 不夠異質？
- 是 quality history 還不夠有差？

## P3.6e 目標

### 研究目標

在真實 coupled trace 上，讓 offline teacher 開始出現非 trivial split decisions。

### 實務目標

建立一個新的 learner-facing bundle，使以下條件至少部分成立：

- `multi_group_ratio` 明顯大於 0
- `positive_gain_count` 明顯大於 0
- learner test split 中也出現真正的多群組 teacher label

### 建議 acceptance gates

P3.6e 不要沿用 P3.6a/P3.6b 的 gate 就滿足，要加新的 decision gate：

1. `full_bundle multi_group_ratio >= 0.05`
2. `full_bundle positive_gain_count >= 20`
3. `learner_test_split multi_group_ratio >= 0.03`
4. `learner_test_split positive_gain_count >= 5`
5. `3+ user snapshots` 佔 learner-facing scenarios 的主體
6. `teacher_gain_vs_single` 的 top cases 不是浮點數平手，而是可解讀的正值

這些數字不是論文最終門檻，但足以當作「終於脫離 trivial regime」的工程 gate。

## P3.6e 場景設計

### A. Overlap 壓力：把 active UE 集中到決策窗口

目前 `p3_6_coupled_scenario/heterogeneous.rou.xml` 的 24 台車分布已經比 smoke 強，
但 teacher audit 顯示 learner-facing snapshots 仍主要只有 `2` 或 `3` 個 UE。

P3.6e 應該讓更多 UE 在相同時間一起接近兩個 gNB 的交界區。

建議：

- 把主要 departure window 從 `0.0s ~ 4.2s` 壓縮到更短，例如 `0.0s ~ 2.4s`
- 增加 central-crossing 路線的車輛比例
- 讓四個方向的車流在 `8s ~ 16s` 左右大量重疊
- 優先製造 `4~8 UE` 同時存在的 learner-facing snapshots

要改的檔案：

- `p3_6e_coupled_scenario/heterogeneous.rou.xml`

### B. Geometry 壓力：讓兩個 gNB 真正形成 center-edge 混合區

目前 gNB 在：

- `gnb_1 = (200, 80)`
- `gnb_2 = (200, 320)`

P3.6e 應該把拓樸調成更容易出現：

- 同一批 UE 中有明顯 center users
- 也有同時存在的 edge users
- handover 前後的瞬間群體不一致

建議方向：

- 保留雙 gNB，但拉開或錯位其中一個 gNB 的位置，形成不對稱覆蓋區
- 讓交會點更接近兩個 cell 邊界，而不是太穩定地偏向其中一個
- 可以考慮讓 `gnb_2` 稍微偏移，不與 `gnb_1` 完全垂直對稱

要改的檔案：

- `p3_6e_gnbs.csv`
- `p3_6e_coupled_scenario/omnetpp.ini`

### C. Radio 壓力：讓 budget 更緊，但不是直接崩掉

P3.6d 顯示目前 `rb_budget_ratio ≈ 0.48` 時，單群組幾乎永遠夠好。

P3.6e 建議不要只保留一個 budget，而是把同一份 raw trace bundle-side 轉成一個小 sweep：

- `rb_budget_ratio = 0.50` 作為 continuity baseline
- `rb_budget_ratio = 0.40`
- `rb_budget_ratio = 0.32`

重點不是盲目重跑矩陣，而是觀察：

- 當 budget 收緊時，teacher 是否開始更常拆群
- 哪個區間最先出現正的 split gain

這個動作不一定要重跑 SUMO/Simu5G；如果 raw radio 已經足夠，就能先在 bundle conversion 層做。

要改的檔案：

- `build_p3_6e_coupled_bundle.py`
- 或複用 `build_p3_5_coupled_bundle.py` 的 `rb_budget_ratio` 參數做小 sweep

### D. Quality-state 壓力：讓群內 switching penalty 真正不一致

P3.6b 已經把 `previous_quality` 從常數變成 deterministic controller，
但目前大多 snapshots 的 quality range 還是很小。

P3.6e 要做的不是回去用隨機 quality，而是讓 deterministic controller 更容易形成異質狀態：

- 不同 UE 因為進場時間不同，初始 buffer / warm-up phase 不一致
- 不同 UE 因為 serving cell / load window 不同，品質回升與下滑節奏不同
- 讓同一 snapshot 中同時存在 `quality = 2/3/4/5` 的組合

建議方向：

- 保留 deterministic controller
- 但加入「進場暖機階段」與「capacity EWMA 記憶」差異
- 讓晚進場 UE 與早進場 UE 不會快速收斂到同一 quality

要改的檔案：

- `simu5g_raw_radio_export.py`

### E. Heterogeneous demand 壓力：不要每台車都像同一種流

目前場景偏向對稱 load。P3.6e 可以引入「需求類型 heterogeneity」，
但不一定要真的實作多種 app module；先從 deterministic controller / export side 做 demand class 也可以。

建議把 UE 分成兩類：

- `conservative-demand users`
  特性：quality 提升較慢，較重視避免 switching

- `aggressive-demand users`
  特性：quality 上升更積極，當 capacity 好時更快衝高 bitrate

這樣一來，即使 CQI 接近，群內也可能因 QoE state 不同而更適合 split。

## 建議的 P3.6e 版本切法

不要一次做一個巨大黑盒改動，建議拆成三個版本：

### P3.6e-1: overlap + geometry

只改：

- route / depart window
- gNB 幾何位置

目的：

- 先確認多 UE 同窗與 center-edge 混合是否足以提高 `multi_group_ratio`

### P3.6e-2: + tighter bundle-side budget

在 e-1 的 raw trace 上，額外做：

- `rb_budget_ratio = 0.40`
- `rb_budget_ratio = 0.32`

目的：

- 找到 teacher 開始偏好 split 的資源壓力區間

### P3.6e-3: + stronger quality-state heterogeneity

在 e-2 的設計上，調整 deterministic controller，使不同 UE 的 previous quality 更不一致。

目的：

- 讓 split decision 不只依賴 radio resource，也會受 switching penalty 影響

## 建議輸出

P3.6e 完成後，至少要固定產出：

- `p3_6e_coupled_bundle/`
- `p3_6e_coupled_audit/`
- `p3_6e_teacher_audit/`
- `P3_6E_SPLIT_PRESSURE_RESULTS_ZH.md`

其中 `teacher audit` 要變成 P3.6e 的主判斷工具，不再只是附帶分析。

## 建議實作順序

### 第一步

先複製 P3.6 場景資產，建立：

- `p3_6e_coupled_scenario/`
- `p3_6e_gnbs.csv`
- `p3_6e_run_split_pressure_coupled.sh`
- `build_p3_6e_coupled_bundle.py`

### 第二步

先只改 route / depart / gNB geometry，做 `P3.6e-1`

### 第三步

跑：

- coupled simulation
- bundle conversion
- `audit_coupled_trace.py`
- `run_p3_6_teacher_decision_audit.py` 的 P3.6e 版本

### 第四步

如果 `multi_group_ratio` 仍幾乎為 0，再加 bundle-side tighter budget，進入 `P3.6e-2`

### 第五步

如果 budget 收緊後仍沒有明顯 `positive_gain_count`，再加 stronger quality-state heterogeneity，進入 `P3.6e-3`

## 這一版設計的成功訊號

如果 P3.6e 是成功的，你會看到：

- `teacher_group_count > 1` 不再是零星偶發
- `teacher_gain_vs_single` 有明顯正值，而不是浮點數平手
- learner-facing split 中也能看到多群組 label
- `pair_sampling` 的 negative pairs 不再幾乎為 0

這時候再進第二輪 learner，才有研究價值。

## 一句話總結

P3.6e 的任務不是「再做一個更複雜的 coupled trace」，
而是刻意把資料推離 single-group trivial regime，讓 offline teacher 在真實 trace 上開始出現有意義的 split decision，
這樣 learner 才真正有東西可學。
