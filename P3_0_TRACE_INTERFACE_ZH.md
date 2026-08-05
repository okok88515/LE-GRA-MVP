# P3.0：SUMO–Simu5G Trace Interface

更新日期：2026-08-05

## 目標

在安裝與整合 SUMO/Simu5G 前，先固定 simulator 與 LE-GRA 之間的資料契約，
避免之後才發現缺少 CQI history、RB-level rate、resource pressure 或 QoE state。

## 完成內容

建立 versioned trace bundle schema v1，由三個 UTF-8 CSV 組成：

1. `scenarios.csv`：timestamp、serving gNB、available/total RB；
2. `users.csv`：UE ID、5-step CQI history、previous quality、位置/移動與 wideband radio欄位；
3. `rb_rates.csv`：per-UE/per-RB rate，以及可選 SINR/CQI。

完整欄位、單位、required/optional 與 simulator source 定義在
`TRACE_SCHEMA.md`。

## 實作

- `trace_io.export_trace_bundle`：將現有 `Scenario` 輸出為標準 bundle；
- `trace_io.load_trace_bundle`：驗證 schema 並重建 `Scenario`；
- 缺少的 Simu5G measurements 寫成空欄位，不製造假資料；
- learner features 不序列化，載入後由 `build_feature_matrix` 重建；
- loader 檢查 schema version、連續 user/RB indices、UE ID mapping、CQI、
  previous quality、RB budget、缺漏/重複/負值 RB rates。

## Round-trip 驗收

以 seed 9 產生 6 個 ambiguous scenarios，交錯使用 light/medium load：

```text
Scenario -> CSV trace bundle -> Scenario
```

結果：

- `cqi_history`、`cqi_now`、`rb_rates`、`previous_quality`：完全一致；
- `distance`、`speed`、`direction_to_gnb`：完全一致；
- `rb_available`：完全一致；
- 最大 absolute error：0.0；
- 6/6 offline-teacher K 與 partition 完全一致；
- 6/6 teacher utility bit-for-bit 一致。

另外移除一筆 RB row 後，loader 正確拒絕資料並回報
`Missing or negative RB rates`，沒有靜默補值。

## 對 SUMO/Simu5G 的要求

SUMO adapter 應提供：

- stable vehicle/UE ID；
- timestamp、x/y、speed；
- UE-to-gNB distance 與 direction；
- 同一 timestamp/gNB 下的同步 UE population。

Simu5G exporter 應提供：

- serving gNB；
- wideband CQI/SINR/RSRP/RSRQ、MCS；
- total/available RB；
- per-RB 或 per-subband SINR/CQI/rate。

若 Simu5G 只能輸出 SINR/CQI，adapter 必須明確記錄轉換為 `rate_kbps` 的
MCS/BLER/overhead mapping。不能用未說明的 synthetic random profile 補足。

## 尚未解決的技術風險

1. Simu5G 是否能在合理成本下匯出 per-RB/per-band channel state；
2. `rb_available` 應取 scheduler 可用 RB、實際配置 RB，或研究控制 budget；
3. CQI reporting interval 與 LE-GRA allocation interval 的對齊；
4. previous quality 與 video traffic/application state 的維護；
5. trajectory-aware train/test split，避免相鄰時間點洩漏。

## P3.0 判定

P3.0 通過。Trace interface 已能隔離 simulator 與 learner，並保持 teacher 行為
完全一致。下一步可以進入 P3.1：建立 SUMO mobility exporter，先輸出 vehicle
trajectory 與 scenario/user tables；radio/RB table 由 P3.2 Simu5G 接手。

