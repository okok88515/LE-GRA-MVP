# P3.5：SUMO + Veins + Simu5G 同步耦合

更新日期：2026-08-06

## 結論

P3.5 已完成第一個真正共用 simulation clock 的 SUMO + Simu5G
end-to-end trace。這不是兩套 simulator 分開執行後再以近似時間合併：SUMO 由
Veins `veins_launchd` 啟動，TraCI 每 0.1 秒更新動態 `NrCar`，OMNeT++/Simu5G
在同一事件排程中計算 radio feedback。

官方 Simu5G `simulations/nr/cars` 的 `VoIP-DL` config 成功跑完 6 秒：

- SUMO 1.22.0
- Veins 5.3.1 + veins_inet
- OMNeT++ 6.3.0
- INET 4.6.0
- Simu5G 1.4.3

P3.5 使用獨立 `/home/opp_env/p3_5_workspace`，不改動 P3.4 已驗證的
OMNeT++ 6.4 workspace。Veins metadata 對 INET 4.6 有舊版白名單 warning，但
`libveins_inet.so` 已編譯成功，官方 NR cars runtime 也完成；因此本階段以實際
compile/run evidence 判定此組合可用。

## Stable ID mapping

P3.5 不假設動態 module index 等於 SUMO vehicle ID。兩個 recorder 使用 OMNeT
module full path 做明確 join：

| SUMO external ID | OMNeT module | Simu5G node ID |
|---|---|---|
| `0` | `Highway.car[0]` | `2049` |
| `1` | `Highway.car[1]` | `2050` |

最終 bundle 的 `ue_id` 只保留 SUMO IDs `0`、`1`，不含 `2049/2050` 或
`ue_2049/ue_2050`。

## Recorder 與時間規則

`veins_p3_5_mobility_recorder.patch` 在 `VeinsInetMobility::nextPosition()` 輸出：

- 同一個 OMNeT `simTime()`
- SUMO external ID
- OMNeT module path
- SUMO/TraCI position 與 speed

`simu5g_p3_5_module_path.patch` 擴充 P3.4 radio recorder，加入同一 module path。
Radio feedback 依 0.1 秒 bins 取每 UE 最後一份完整 observation，再只保留存在
mobility observation 的 `(timestamp, module)`。這使 P3.2 仍可使用 exact
timestamp join，沒有 nearest-time 猜測。

## 實際 acceptance 結果

Coupled raw output：

- Mobility rows：67
- Radio rows：27,950
- SUMO vehicles：2
- Radio snapshots：1,118
- 每份 radio snapshot：完整 25 logical bands
- Serving gNB：`gnb_1`

同步與正規化後：

- Mapped radio rows：27,100
- Normalized radio user rows：67
- Normalized radio RB rows：1,675
- CQI-history warm-up exclusions：8 user rows
- P3.0 scenarios：55
- P3.0 user rows：59
- P3.0 RB rows：1,475
- Offline teacher：55/55 scenarios 成功執行

驗證指令：

```powershell
wsl -d LE-GRA-opp-env -- bash --noprofile --norc `
  /c/Users/User/Documents/LE-GRA-MVP/p3_5_check_environment.sh

wsl -d LE-GRA-opp-env -- bash --noprofile --norc `
  /c/Users/User/Documents/LE-GRA-MVP/p3_5_apply_recorders.sh

wsl -d LE-GRA-opp-env -- bash --noprofile --norc `
  /c/Users/User/Documents/LE-GRA-MVP/p3_5_run_coupled_smoke.sh

python -u .\run_p3_5_coupled_test.py
```

## 目前不能過度解讀的地方

P3.5 證明 coupling、ID mapping、time alignment、25-band completeness、P3.2 join
與 teacher execution 都成立，但尚不是可用來回答 learner research question 的
資料集：

1. 6 秒內只有 2 台車，主要是 integration smoke test。
2. 目前 radio CQI 全為 15，沒有足夠 channel/resource ambiguity。
3. `previous_quality=3` 仍是 metadata 明確標示的 experiment control，不是 video
   application 實測狀態。
4. gNB 位置由官方 Highway NED display coordinates 匯出至 `p3_5_gnbs.csv`；換
   network 時必須重新產生，不可沿用。
5. Per-band SINR 仍未輸出，但 CQI 與 NR TBS rate matrix 已完整。

## 建議 P3.6

下一步先改善資料語意，而不是擴大 Kmax/seeds：

1. 建立較長但仍小型的 coupled scenario，加入不同距離、遮蔽/干擾與 handover。
2. 驗證 wideband CQI 相近時，per-band TBS profiles 確實不同。
3. 加入 video application state recorder，取代固定 `previous_quality`。
4. 做 coupled-data audit（使用者數、CQI/TBS dispersion、load、handover、QoE）。
5. Audit 通過後才建立第一個 learner-focused real-trace experiment。
