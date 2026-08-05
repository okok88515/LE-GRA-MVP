# P3.4：Simu5G Per-Band Radio Exporter

更新日期：2026-08-06

## 結論

P3.4 已從真實 Simu5G 執行流程輸出 LE-GRA 所需的 per-UE/per-logical-band
channel state，不再依賴 synthetic radio fixture。Recorder 位於 gNB MAC 收到
`ALLBANDS` feedback 並更新 AMC 的位置，因此尚未被 scheduler 排到該 band 的 UE
也有 counterfactual CQI/TBS，不會只觀察到實際獲配置的 RB。

Simu5G 原始碼修改以 `simu5g_p3_4_radio_recorder.patch` 保存，不把整份 Simu5G
source tree 放進本專案。`p3_4_apply_and_build.sh` 可重複套用 patch 並增量編譯。

## Rate 語意

Recorder 對每個 UE、logical band 呼叫 Simu5G 的
`NrAmc::computeBitsPerRbBackground(cqi, DL, carrierFrequency)`，取得單一 NR slot
可承載的 transport-block bits。該實作採用 Simu5G 的 NR MCS/TBS 邏輯，其註解
標明依據 3GPP TS 38.214。

Raw 欄位為：`timestamp_s`、`ue_node_id`、`gnb_node_id`、`band_index`、
`cqi`、`tbs_bits_per_slot`、`total_bands`。

Python exporter 使用明確指定的 slot duration：

```text
rate_kbps = tbs_bits_per_slot / slot_duration_ms
```

目前 NR tutorial 使用 numerology 0，驗證時明確指定 `slot_duration_ms=1.0`。
若日後改 numerology，必須同步改參數，不可沿用 1 ms。

## 時間同步與資源壓力

原始 feedback 約每 6 ms 到達。`simu5g_raw_radio_export.py` 把 timestamp 依指定
study interval 向下分 bin，對每個 UE 取該 bin 最後一份完整 feedback，讓 P3.2
可以使用 exact timestamp join。驗證使用 0.1 s interval。

`rb_available` 仍是 LE-GRA 實驗控制的 offered-load/resource-pressure budget，
不是 scheduler 已分配給單一 UE 的 RB 數。驗證使用 50%，即 6 個 logical bands
中可用 3 個。所有轉換參數與來源都寫入 `export_metadata.json`。

## 實際結果

Single-UE 無干擾案例執行 2 s，產生 2,004 raw rows、334 份完整 6-band
snapshots；CQI 皆為 15，TBS 為 1,160 bits/slot。這只用於確認管線完整性，
不適合拿來訓練 learner。

官方 `Multiple-UEs` 的 5-UE + background interference 小案例同樣執行 2 s：

- 10,020 raw rows、1,670 份完整 6-band UE snapshots。
- Normalized 結果為 105 user rows 與 630 RB rows。
- 實際 CQI 為 9、13、14、15。
- 對應 TBS 為 608、984、1,128、1,160 bits/slot。
- 已觀察到 cross-user 與同一 UE 的 per-band 差異。

執行：

```powershell
wsl -d LE-GRA-opp-env -- bash --noprofile --norc `
  /c/Users/User/Documents/LE-GRA-MVP/p3_4_apply_and_build.sh

wsl -d LE-GRA-opp-env -- bash --noprofile --norc `
  /c/Users/User/Documents/LE-GRA-MVP/p3_4_run_multi_ue_recorder.sh

python -u .\run_p3_4_export_test.py
python -u .\run_p3_4_multi_ue_validation.py
```

## 限制與下一步

P3.4 完成的是 radio exporter，不代表 SUMO+Simu5G end-to-end data 已完成：

1. `ue_node_id` 是 Simu5G internal node ID，尚未對應 SUMO vehicle ID。
2. P3.4 使用 Simu5G feedback clock 分 bin，尚未和 SUMO/TraCI 共用時間來源。
3. `previous_quality=3` 是明確標示的實驗控制值，不是 video application 實測狀態。
4. Per-band SINR 尚未輸出；CQI 與 NR TBS 已足以建立必要 rate matrix，但 SINR
   diagnostics 仍可補強。
5. Logical band 與 physical RB 的關係必須隨 carrier configuration 一起記錄。

因此 P3.5 應優先建立最小 SUMO+Simu5G coupled scenario、stable ID mapping 和共同
timestamp，再加入真實 video quality state。此時仍不應擴大 Kmax、seeds 或整體
實驗矩陣。
