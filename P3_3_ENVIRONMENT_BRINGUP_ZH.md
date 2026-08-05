# P3.3：Simu5G 環境建置與實際訊號盤點

更新日期：2026-08-05

## 結論

P3.3 已完成真實 Simu5G 執行環境的 bring-up，不再只是 fixture 或 schema
層級驗證。官方 NR `Single-UE` tutorial 已以 Cmdenv 成功跑完 10 秒模擬，處理
92,628 個 events，並產生非空的 `.sca`、`.vec` 與 `.vci` 結果。

目前環境版本為：

- WSL distribution：`LE-GRA-opp-env`
- opp_env：`0.36.1.20260515`
- OMNeT++：`6.4.0`
- INET：`4.6.0`
- Simu5G：`1.4.3`

這些版本由 `opp_env install simu5g-1.4.3` 解出相容相依套件。大型 simulator
安裝內容留在 `.sim-env/` 與 WSL filesystem，不納入 Git。

## 實際驗證

環境檢查：

```powershell
wsl -d LE-GRA-opp-env -- bash --noprofile --norc `
  /c/Users/User/Documents/LE-GRA-MVP/p3_3_env_check.sh
```

執行官方 NR tutorial：

```powershell
wsl -d LE-GRA-opp-env -- bash --noprofile --norc `
  /c/Users/User/Documents/LE-GRA-MVP/p3_3_run_single_cell.sh
```

檢查結果與訊號：

```powershell
wsl -d LE-GRA-opp-env -- bash --noprofile --norc `
  /c/Users/User/Documents/LE-GRA-MVP/p3_3_audit_signals.sh
```

較完整的 qualified result name 列表可用 `p3_3_inspect_results.sh` 查看。

## P3.2 schema 的欄位可得性

標準結果已確認包含：

- `averageCqiDl/Ul`：UE wideband average CQI，可建立 CQI history。
- `measuredSinrDl/Ul` 與 `rcvdSinrDl/Ul`：feedback 計算或封包接收時的 SINR。
- `avgServedBlocksDl/Ul`：scheduler 實際配置 RB 數的平均值。
- HARQ error/attempt、MAC/RLC throughput、delay 與 packet loss。

但 `avgServedBlocks` 只描述實際排程結果，不能替代 P3.2 `radio_rbs.csv` 要求的
完整 `(timestamp, UE, RB index) -> achievable payload rate` 矩陣。該矩陣必須讓
offline teacher 比較「尚未被排到該 RB 的 UE 如果使用該 RB 能得到多少 rate」；
只輸出已配置 RB 或平均 CQI 會造成 selection bias，也會把 ambiguous 場景所需的
frequency-selective 差異抹掉。

## P3.3 判定

P3.3 通過：工具鏈、binary/library、官方案例及標準 radio signals 均已實際驗證。
P3.2 joiner 尚不能直接吃原生 `.vec/.sca`，因為缺少 per-UE/per-RB
counterfactual rate exporter。下一步 P3.4 應做最小 custom recorder/exporter：

1. 固定同一 simulation timestamp 與 stable UE ID。
2. 輸出 serving gNB、wideband CQI/SINR 與 total/available RB budget。
3. 從 channel/feedback state 輸出每 UE、每 logical band/RB 的 achievable rate。
4. 明確記錄 logical band 到 physical RB 的映射與 rate 單位。
5. 先用 1 gNB、少量 UEs 做 adapter end-to-end acceptance，不擴大 seeds/Kmax。

SUMO coupling 暫不在 P3.3 內啟動；先確保 radio exporter 的語意正確，才不會把
mobility integration 與 radio extraction 兩種問題混在一起。
