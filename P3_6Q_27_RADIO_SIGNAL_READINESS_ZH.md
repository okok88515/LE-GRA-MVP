# P3.6q-27 radio-signal readiness 檢查

## 背景

前一輪我們已經把研究問題收斂到：

- `q23/q26` 的主 bottleneck 是 `28.3s` earliest crossover onset
- 現有 learner 已經不只是看純 CQI
- 但仍然可能缺少更連續、更早期的 radio-quality 訊號

因此這一輪的目標不是立刻重跑 learner matrix，而是先回答一個更基本的問題：

- 我們手上的 coupled traces 到底有沒有 `RSRP / RSRQ / SINR / MCS` 可用？

## 這一輪實作

### 1. 補齊 radio-aware feature pipeline

已完成最小向後相容實作：

- `simu5g_raw_radio_export.py`
  - 現在若 raw radio 含有 optional 欄位，會保留：
    - `sinr_db`
    - `wideband_sinr_db`
    - `rsrp_dbm`
    - `rsrq_db`
    - `mcs`
  - 並把 `available_optional_raw_fields` 寫進 `export_metadata.json`
- `trace_io.py`
  - 現在會把上述欄位讀回 `Scenario`
- `run_p3_6_coupled_learner.py`
  - 補齊新 `Scenario` 欄位，避免舊 focused learner 腳本壞掉
- `le_gra_mvp.py`
  - 新增 `Scenario` radio 欄位
  - 新增 feature modes：
    - `history_cost_radio`
    - `full_radio_context`

### 2. 新增 radio coverage audit 工具

新增：

- `audit_radio_signal_coverage.py`

用途：

- 檢查 bundle 的 `radio/` 與 `bundle/` 表格中，optional radio 欄位到底有多少非空覆蓋率

## 實際檢查結果

### 主研究 regime：`p3_6q23_dual_boundary_crossover_bundle`

artifact:

- `p3_6q27_q23_radio_coverage.csv`

結果：

- `radio_users.wideband_sinr_db = 0 / 3243`
- `radio_users.rsrp_dbm = 0 / 3243`
- `radio_users.rsrq_db = 0 / 3243`
- `radio_users.mcs = 0 / 3243`
- `radio_rbs.sinr_db = 0 / 81075`
- `bundle_users.wideband_sinr_db = 0 / 3203`
- `bundle_users.rsrp_dbm = 0 / 3203`
- `bundle_users.rsrq_db = 0 / 3203`
- `bundle_users.mcs = 0 / 3203`
- `bundle_rb_rates.sinr_db = 0 / 80075`

結論：

- `q23` 主研究 bundle 的 optional radio signals 覆蓋率是 `0%`

### 最早 coupled baseline：`p3_5_coupled_bundle`

artifact:

- `p3_6q27_p35_radio_coverage.csv`

結果同樣是：

- `wideband_sinr_db / rsrp_dbm / rsrq_db / mcs / sinr_db` 全部 `0%`

結論：

- 這不是 `q23` 特例
- 而是目前 repo 內既有 coupled-radio bundle 普遍都還沒有把這些訊號真正錄下來

## 這代表什麼

這一輪把問題切得更清楚了：

1. 現在不是「模型還沒好好利用 radio-power/SINR」
2. 而是「目前資料集根本沒有這些值」
3. 所以此刻直接跑 `history_cost_radio` 或 `full_radio_context`，只會退化成舊特徵加上一堆全零欄位

換句話說：

- radio-aware learner path 現在已經 ready
- 但 radio-aware dataset 還沒有 ready

## 目前最合理的下一步

下一步應該從 **Simu5G recorder source** 下手，而不是先做 learner sweep：

1. 擴充 recorder patch，讓 raw radio 真正輸出：
   - per-band `sinr_db`
   - per-UE wideband `sinr_db`
   - `rsrp_dbm`
   - `rsrq_db`
   - `mcs`
2. 重跑最小 coupled smoke / `p3_5` bundle
3. 先再次跑 `audit_radio_signal_coverage.py`
4. 只有在 coverage 不再是 `0%` 之後，才值得做：
   - `history_cost_radio`
   - `full_radio_context`
   - focused `q23/q26` onset validation

## 目前最重要的一句話

`radio-aware learner support is now implemented, but radio-aware coupled data is still missing.`
