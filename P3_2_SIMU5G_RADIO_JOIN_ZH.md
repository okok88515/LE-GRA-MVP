# P3.2：Simu5G Radio Schema 與 SUMO Join

更新日期：2026-08-05

## 目標

定義 Simu5G/OMNeT++ radio exporter 的最小資料契約，並驗證 P3.1 SUMO
mobility staging 可以與 radio observations 結合，產生 P3.0 完整 trace bundle，
直接供現有 LE-GRA learner 與 offline teacher 使用。

## 環境與宣稱範圍

目前本機沒有 OMNeT++、INET 或 Simu5G，因此 P3.2 完成的是 normalized radio
schema、join/validation pipeline 與 deterministic fixture integration；尚未完成
實際 Simu5G executable run。

Simu5G 官方目前要求 OMNeT++ 6.0.3+ 與 INET 4.5+。OMNeT++ 一般將 time-series
輸出為 `.vec`、summary 輸出為 `.sca`。現有標準 statistics 不保證包含 LE-GRA
需要的完整 per-RB matrix，所以實際整合可能需要：

- 啟用特定 Simu5G vector recording；
- 用 `opp_scavetool` 正規化 vector output；或
- 增加小型 custom recorder/exporter。

## Radio schema

`SIMU5G_RADIO_SCHEMA.md` 定義兩張表：

### `radio_users.csv`

- timestamp、UE ID、Simu5G serving gNB；
- wideband CQI/SINR、RSRP、RSRQ、MCS；
- previous quality；
- total RBs 與 LE-GRA 可用 RB budget。

### `radio_rbs.csv`

- timestamp、UE ID、serving gNB、RB index；
- achievable payload rate；
- optional per-RB SINR/CQI。

Simu5G serving association 會覆蓋 P3.1 nearest-gNB heuristic；nearest-gNB 只作
mobility staging 與 sanity check。

## Join pipeline

`simu5g_trace_io.build_trace_bundle`：

1. 以 exact `(timestamp, UE ID)` 對齊 SUMO 與 Simu5G；
2. 保持 stable UE trajectory；
3. 以每個 UE 最近 5 筆 wideband CQI 建立 history；
4. 移除不足 5-step history 的 warm-up rows；
5. 依 Simu5G `(timestamp, serving gNB)` 建立 scenario；
6. 驗證同 scenario 的 total/available RB 一致；
7. 驗證每個 UE 有完整、連續且非負的 RB-rate vector；
8. 輸出 P3.0 `scenarios.csv/users.csv/rb_rates.csv`；
9. 由 P3.0 loader 重建 `history_cost_quality` features。

Schema v1 採 exact timestamp join。若實際 SUMO/Simu5G recorder clocks 無法完全
一致，應在 exporter 層使用同一 simulation time source；不優先用模糊 nearest
time join，以免把不同 scheduling interval 錯配。

## Fixture 驗收

測試資料：

- 1 gNB；
- 2 stable UEs；
- 6 timestamps；
- 4 RBs；
- 前 4 timestamps 作 CQI-history warm-up；
- 最後 2 timestamps 形成完整 allocation scenarios；
- RB budget 從 3 改為 2，驗證 resource pressure 可隨時間變化。

結果：

- final scenarios：2；
- final users：4 rows；
- final RB observations：16 rows；
- warm-up exclusions：8 user rows；
- CQI histories 完全符合預期；
- `history_cost_quality` 維度為 12；
- time-varying RB budget 正確保留；
- P3.0 loader 成功；
- offline teacher 可在兩個 joined scenarios 正常執行；
- 刻意移除一筆 RB row 後，joiner 正確回報 incomplete RB vector。

## 使用方式

```powershell
python -u .\join_sumo_simu5g.py `
  --mobility-dir sumo_mobility_staging `
  --radio-dir simu5g_radio_export `
  --min-users 24 --max-users 24 `
  --out-dir sumo_simu5g_trace_bundle
```

## 仍待實際 Simu5G 確認

1. UE module path 與 SUMO vehicle ID 的 mapping；
2. serving-cell association signal；
3. wideband CQI feedback signal與 reporting interval；
4. per-band/per-RB SINR 或 achievable bytes/rate 的可取得位置；
5. scheduler 中 total RB、已占用 RB與研究 budget的語意；
6. video application如何維護 previous quality；
7. logical band 與 physical RB的 mapping及 rate overhead。

## P3.2 判定

P3.2 schema 與離線 join integration 通過，但 actual Simu5G run 尚未驗證。下一步
應是 P3.3 environment bring-up：固定相容版本、跑官方 single-cell example、列出
實際 `.vec/.sca` signals，再決定用設定、`opp_scavetool` 或 custom recorder輸出
兩張 normalized radio tables。

