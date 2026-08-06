# P3.6c Coupled Trace 第一輪 Learner 結果

更新日期：2026-08-06

## 這一輪做了什麼

我們在 `p3_6_coupled_bundle/bundle/` 上建立第一輪真實 coupled trace learner 測試，
新增腳本：

- `run_p3_6_coupled_learner.py`

這個腳本做四件事：

1. 讀取 coupled bundle 的 `scenarios.csv`、`users.csv`、`rb_rates.csv`
2. 以 `ue_id` 做 trajectory-aware split，避免同一台 UE 的時間序列同時出現在 train/test
3. 用 offline teacher 產生訓練標籤，再訓練第一版 learner
4. 比較六種方法在 coupled trace 上的表現，並輸出 teacher-imitation diagnostics

## 目前輸出檔案

輸出目錄：`p3_6_coupled_learner/`

- `split_summary.json`
- `train_scenarios.csv`
- `test_scenarios.csv`
- `main_comparison.csv`
- `teacher_imitation_diagnostics.csv`

## 資料切分

- train UE：`1, 11, 17, 23, 3, 4, 5`
- test UE：`0, 16, 2`
- train scenarios：`561`
- test scenarios：`311`
- test user-count 分布：`2-user = 164`, `3-user = 147`
- `rb_budget_ratio = 0.5`

這個切分代表：

- 我們已經不是在 synthetic matrix 上玩，而是真的讓 learner 面對 coupled trace
- 但目前 test snapshot 還只落在 2~3 個 UE 的小規模子場景

## 訓練結果

- feature mode：`history_cost_quality`
- `Kmax = 3`
- epochs：`12`
- seed：`9`
- selected epoch：`12`
- best training loss：`0.002958`
- pair sampling：`random_balanced`

訓練期的 pair 統計有一個很重要的訊號：

- 平均 positive pairs：`2.806`
- 平均 negative pairs：`0.029`
- active negative ratio：`0.007`
- mean selected negative distance：`0.049`

這表示目前 learner 幾乎沒有看到足夠的「應該分開」的負樣本，監督訊號非常弱。

## 第一輪主結果

`main_comparison.csv` 的六個方法結果完全相同：

- `No grouping`
- `CQI k-means`
- `Resource-cost k-means`
- `Multi-feature k-means`
- `Offline teacher`
- `LE-GRA MVP`

共同結果：

- utility：`0.7595`
- ADR：`5800 kbps`
- system spectral efficiency：`6.6396`
- served ratio：`1.0`
- average quality：`4.0`
- switching：`0.3391`
- fairness：`1.0`
- average groups：`1.0`

## Teacher-imitation diagnostics

在 `teacher_imitation_diagnostics.csv` 中：

- `LE-GRA MVP` 平均 `pairwise_accuracy = 1.0`
- `LE-GRA MVP` 平均 `ARI = 1.0`
- `LE-GRA MVP` 平均 `NMI = 1.0`
- `Multi-feature k-means` 也同樣全部 `1.0`
- 兩個方法在 `311/311` 個 test scenarios 中都只輸出 `1 group`

這不是 learner 已經完全解決問題，而是：

- offline teacher 本身在這批 coupled snapshots 上也總是選 `1 group`
- 所以所有方法都落在同一個 trivial policy

## 目前最重要的研究解讀

### 1. 第一輪 learner pipeline 已經打通

這是這一輪最實際的成果。  
我們已經證明：

- coupled bundle 可以直接餵進 learner
- 可以做 UE-level trajectory split
- 可以訓練、評估、輸出 diagnostics

所以 P3.6 後面如果要做 learner-facing 真實資料研究，技術管線已經成立。

### 2. 現在的 coupled trace 還沒有形成真正的 grouping 壓力

雖然 P3.6a/P3.6b 已經把資料變得比前一版有資訊很多，
但目前這一輪 test set 仍然出現：

- teacher 永遠選單一群組
- 所有 baseline 永遠選單一群組
- learner 也永遠選單一群組

所以現在還看不到「誰比較會分群」，只能看到「目前沒有必要分群」。

### 3. learner 沒有失敗，但也還沒有被真正考驗

如果所有方法都輸出一樣的單群組，那麼：

- `ARI = 1.0`
- `NMI = 1.0`
- `pairwise_accuracy = 1.0`

都只表示大家在 trivial policy 上一致，不能解讀成 learner 已經學會複雜 grouping。

### 4. 真正的瓶頸不是模型，而是場景的 decision diversity

目前資料仍然讓 teacher 幾乎不需要做 partition tradeoff。  
研究上更關鍵的下一步不是先擴大 learner，而是讓 coupled trace 裡真的出現：

- 有些 snapshot 應該合併
- 有些 snapshot 應該拆開
- 不同方法會做出不同決策

這樣 learner 的價值才看得出來。

## 下一步建議

### 收斂方向

先做 `teacher-decision audit`，直接量化 offline teacher 到底是不是幾乎永遠選單群組：

- 每個 snapshot 的 `teacher_group_count`
- `teacher_group_count > 1` 的比例
- 不同 `user_count` 下的分布
- 不同 `serving_gnb` / `rb_available` / `previous_quality` 區間下的分布

### 發散方向

如果 audit 證明 teacher 幾乎永遠單群組，那下一輪應優先增加「需要拆群」的場景壓力，例如：

- 更高 UE overlap
- 更明顯的 cell-edge / cell-center 混合
- 更強的 per-band capacity dispersion
- 更長時間的 congestion / handover / quality fluctuation

### 暫時不要先做的事

在目前這個結果下，不建議先做：

- 擴大 `Kmax`
- 擴大 seeds
- 擴大 learner matrix
- 調很多模型超參數

因為現在主要不是 learner 分不出來，而是資料還沒有逼出需要分群的決策差異。

## 一句話總結

P3.6c 的價值不是「learner 贏了」，而是我們第一次確認：
真實 coupled trace learner pipeline 已經能跑通；但目前資料仍偏向 trivial single-group regime，
下一步應先審核 teacher 決策分布，再決定要加強哪種 coupled 場景壓力。
