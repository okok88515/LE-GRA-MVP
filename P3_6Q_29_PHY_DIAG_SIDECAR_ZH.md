# P3.6q-29 UE-PHY radio diagnostics sidecar

日期：2026-08-10

## 這一步做了什麼

在 `q-28` 我們已經確認：

- `SINR` / `RSRP` 真正存在於 UE PHY / feedback computation path
- 直接把這些狀態硬塞回既有 `LteMacEnb.cc` recorder 風險較高

所以這一步改採 sidecar 策略：

1. 保留原本 `raw_radio.csv` 當主表
2. 在 `LtePhyEnb.cc` 額外輸出 `raw_radio_diag.csv`
3. 在 repo 端的 `simu5g_raw_radio_export.py` 依
   `(timestamp_s, ue_node_id, gnb_node_id, band_index)`
   自動合併 sidecar

## 新增的資料流

### WSL source patch

新增：

- `p3_6q29_apply_phy_radio_diag_recorder.sh`

它會在 `LtePhyEnb.cc` 中加入：

- `LEGRA_RADIO_DIAG_RAW_CSV` sidecar writer
- 每次 DL feedback 生成時輸出：
  - `sinr_db`
  - `wideband_sinr_db`
  - `rsrp_dbm`

sidecar header 為：

```text
timestamp_s,ue_node_id,gnb_node_id,band_index,sinr_db,wideband_sinr_db,rsrp_dbm
```

### Repo merge

`simu5g_raw_radio_export.py` 現在支援：

- `raw_diag_csv` 顯式參數
- 若未顯式指定，會自動尋找 sibling sidecar：
  - `raw_radio_diag.csv`
  - 或 `<stem>_diag.csv`

只要 sidecar 存在，exporter 就會先把這些欄位 merge 回主 raw rows：

- `sinr_db`
- `wideband_sinr_db`
- `rsrp_dbm`

## 為什麼這樣拆比較好

這個設計有三個好處：

1. 不需要改既有 `LteFeedback` message schema
2. 不需要在 PHY 與 MAC 間維護額外共享 cache
3. exporter 端仍然維持 backward-compatible

也就是說：

- 舊資料照樣能跑
- 新資料一旦有 sidecar，就能自動長出 continuous radio fields

## 本輪同步更新

### Export / bundle

- `simu5g_raw_radio_export.py`
- `build_p3_5_coupled_bundle.py`

### Recorder / run scripts

這些腳本現在會一起導出 `raw_radio_diag.csv`：

- `p3_4_run_recorder.sh`
- `p3_4_run_multi_ue_recorder.sh`
- `p3_5_run_coupled_smoke.sh`
- `p3_6_run_informative_coupled.sh`
- `p3_6e_run_split_pressure_coupled.sh`
- `p3_6i_run_targeted_family_coupled.sh`
- `p3_6i2_run_targeted_family_coupled.sh`

## 下一步

1. 先在公司機跑：
   - `p3_6q29_apply_phy_radio_diag_recorder.sh`
2. 跑一個最小 smoke test
3. 確認：
   - `raw_radio_diag.csv` 存在
   - exporter 後的 `radio_users.csv / radio_rbs.csv`
     已經開始有非空的
     `wideband_sinr_db / rsrp_dbm / sinr_db`
4. 只有在 coverage 非零後，才回 `q23/q26` 做 learner focused validation
