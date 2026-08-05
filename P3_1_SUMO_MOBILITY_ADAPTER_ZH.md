# P3.1：SUMO Mobility Adapter

更新日期：2026-08-05

## 目標

將 SUMO Floating Car Data（FCD）轉成 P3.2 Simu5G 可以補上 radio state 的
mobility staging tables，同時保持 UE ID、時間與 gNB assignment 可追查。

## 環境狀態

目前工作電腦未安裝 `sumo`、`traci` 或 `sumolib`。因此本階段沒有宣稱執行
完整 SUMO simulation；adapter 使用 Python standard library 直接解析 SUMO
官方 FCD XML 格式，並以 deterministic fixture 驗證。實際 SUMO 安裝後只需將
`--fcd-output` 指向 exporter，不需要更改 learner 或 trace contract。

## 完成內容

- `SUMO_MOBILITY_SCHEMA.md`：定義 FCD、gNB 與 staging CSV schema；
- `sumo_mobility_io.py`：streaming XML parser 與 mobility exporter；
- `sumo_fcd_to_mobility.py`：command-line converter；
- `p3_1_fixture/`：兩個 gNB、四輛車、兩個 timestamps 的測試資料；
- `run_sumo_mobility_test.py`：P3.1 acceptance test。

## Adapter 行為

1. 讀取每個 timestep 的 vehicle ID、x/y、speed、angle 與可選 lane metadata；
2. 將 UE 指派給歐氏距離最近的 configured gNB；
3. 以 `(timestamp, serving_gnb)` 建立同步 snapshot；
4. 計算 UE-to-gNB distance；
5. 按 SUMO navigation angle 計算 direction-to-gNB cosine；
6. 保留跨時間 stable UE ID 與 trajectory step；
7. 支援 `--min-users` 移除過小 snapshots；
8. 支援 `--max-users` 依距離 deterministic 選取最近 UEs。

P3.1 不產生 CQI、SINR、RB rate、RB budget 或 previous quality。這些欄位由
P3.2 Simu5G/application adapter提供，避免將 mobility-only output 偽裝成完整
5G dataset。

## 驗收結果

Fixture 的 uncapped export：

- 2 timestamps；
- 2 gNBs；
- 4 snapshots；
- 7 mobility rows；
- 4 stable UE IDs。

已驗證：

- `veh0` 兩個時間點的 trajectory steps 為 0、1；
- 朝 gNB 行進的 direction 為 +1；
- 遠離 gNB 為 -1；
- speed=0 的 UE direction 定義為 0；
- `min_users=2, max_users=2` 保留 3 個 snapshots、6 rows；
- capped UE selection 與 user indexing 可重現。

## 使用方式

SUMO 產生 FCD 後執行：

```powershell
python -u .\sumo_fcd_to_mobility.py `
  --fcd path\to\mobility.fcd.xml `
  --gnbs path\to\gnbs.csv `
  --min-users 24 `
  --max-users 24 `
  --out-dir sumo_mobility_staging
```

輸出：

- `sumo_scenarios.csv`
- `sumo_mobility.csv`

## 限制與下一步

Nearest-gNB assignment 是 P3.1 的 deterministic mobility rule。P3.2 若能取得
Simu5G serving-cell association，應以 Simu5G 結果為準並檢查兩者差異。

下一步 P3.2：

1. 建立 Simu5G radio-export schema；
2. 確認可取得的 CQI/SINR/MCS granularity；
3. 依 timestamp、UE ID、serving gNB 與 mobility staging 對齊；
4. 補齊 five-step CQI、previous quality、RB budget、per-RB/subband rate；
5. 產生並通過 P3.0 full trace bundle loader。

## P3.1 判定

P3.1 adapter 與離線格式驗證通過；實際 SUMO executable run 尚待安裝環境後
驗證。這個限制不阻塞 P3.2 schema 與 Simu5G exporter 設計。

