# P3.6q-28 Source-hook audit 與 recorder 擴充分層策略

日期：2026-08-10

## 這一步在回答什麼

在 `P3.6q-27` 我們已經把 learner 端的 radio-aware feature path 接好了，但現有 coupled bundle 的
`wideband_sinr_db / rsrp_dbm / rsrq_db / sinr_db / mcs` 覆蓋率仍然是 `0%`。

所以這一步不再碰 learner，而是直接往 Simu5G source 追：

1. 目前 recorder 已經在哪裡掛 hook？
2. `SINR / RSRP / RSRQ / MCS` 分別能不能在低成本下拿到？
3. 應該先做哪一層擴充，才不會又陷入「欄位很多但沒有真正可重建資料」的空轉？

## Source audit 結果

### 1. eNB MAC 端目前確定能穩定拿到什麼

目前 `p3_5_apply_recorders.sh` 掛在 `LteMacEnb.cc` 的 DL feedback 處理路徑。

從 `LteFeedback.h` 可確認：

- feedback 內建有 `hasBandCqi() / getBandCqi()`
- feedback 內建也有 `hasWbCqi() / getWbCqi()`

也就是說，除了現在已經輸出的 per-band `cqi` 之外，
eNB MAC 其實還能直接拿到：

- `wideband_cqi`

另外從 `LteAmc.h` 可確認：

- `LteAmc::getItbsPerCqi(cqi, dir)` 是公開方法

所以 recorder 也可以從每個 band 的 `cqi` 直接推回：

- `itbs`

這兩個欄位不需要改 UE PHY 路徑，也不需要額外改 message schema，
屬於「今天就能安全補上的第一層擴充」。

### 2. per-band SINR / wideband SINR 在哪裡

從 `LteRealisticChannelModel.h` 可確認 channel model 已提供：

- `getSINR(...)`
- `getRSRP(...)`

從 `LteFeedbackComputationRealistic.cc` 可確認：

- feedback 生成時已經收到 `std::vector<double> snr`
- `WIDEBAND` CQI 是由 `meanSnr(snr)` 後再映射成 CQI
- `ALLBANDS` CQI 則是逐 band 對 `snr[j]` 做 CQI 映射

這代表：

- `per-band SINR` 真正存在於 PHY feedback computation path
- `wideband SINR` 也存在，因為 `meanSnr(snr)` 已經明確被計算

所以如果要拿真正連續值、而不是只有 CQI index，
最合理的第二層擴充不是再改 eNB MAC，而是要在
`LteFeedbackComputationRealistic` 或 UE PHY feedback send path
加 recorder hook。

### 3. RSRP 在哪裡

從 `LtePhyUe.cc` 與 `LteRealisticChannelModel` 可確認：

- UE 在 cell search / handover 相關流程中會呼叫 `getRSRP(...)`

這代表 `rsrp_dbm` 也不是不存在，
但它不像 CQI 一樣已經被塞進目前送到 eNB 的 feedback object。

所以 `RSRP` 的結論和 `SINR` 類似：

- 有 source hook
- 但屬於 UE PHY / channel model 層
- 不適合只靠現在的 `LteMacEnb.cc` recorder 直接補齊

### 4. RSRQ 的狀況

這輪 source grep 幾乎找不到可直接重用的 `RSRQ` hook。

目前最保守的判斷是：

- `RSRQ` 不是完全不可能
- 但至少在現有 recorder 路線上，沒有像 `SINR / RSRP` 那樣清楚的低成本入口

因此不應該把 `RSRQ` 當成第一優先欄位。

## 研究決策：把擴充分成兩層

### Layer 1：先補 eNB MAC 可立即取得的 richer diagnosis

這一層先補：

- `wideband_cqi`
- `itbs`

這不是最終想要的 continuous radio signal，
但它有三個價值：

1. 幾乎零風險，不需要重構 PHY path
2. 可讓 raw radio 不再只剩 `band cqi + tbs`
3. 幫我們驗證 recorder v2 rebuild 流程是否順

本輪已在 repo 內加入：

- `p3_6q28_apply_radio_recorder_v2.sh`

用途是把已經套過舊版 recorder 的 `LteMacEnb.cc`
升級成會多輸出 `wideband_cqi,itbs` 的版本。

另外 `p3_5_apply_recorders.sh` 也已同步更新，
讓未來從乾淨環境安裝時直接落在新版 header。

### Layer 2：真正要拉開 learner 差距的關鍵擴充

真正值得期待的欄位仍然是：

- `per-band sinr_db`
- `wideband_sinr_db`
- `rsrp_dbm`

原因很直接：

- 這些是連續值，不像 CQI 只有 `1~15`
- `LteFeedbackComputationRealistic` 已證明它們在 mapping 成 CQI 前就存在
- 如果 learner 真的被 CQI 量化壓扁，這些欄位才有機會把差距穩定放大

所以 q-28 的真正結論不是「已經拿到 power-based signals」，
而是：

> 我們已經把 source hook 位置查清楚了，下一步應該正式做 UE PHY / feedback-computation recorder，
> 而不是再在 learner 端猜測 feature。

## 本輪實作結果

### 已完成

1. learner 端 radio-aware path 已在 `q-27` 完成
2. 本輪完成 source-hook audit
3. 新增 `p3_6q28_apply_radio_recorder_v2.sh`
4. 更新 `p3_5_apply_recorders.sh`
   - 新安裝時直接輸出 `wideband_cqi,itbs`

### 尚未完成

1. UE PHY / feedback computation recorder
   - `sinr_db`
   - `wideband_sinr_db`
   - `rsrp_dbm`
2. 用新 recorder 重跑一個小型 raw radio
3. 再次執行 `audit_radio_signal_coverage.py`
4. 在 coverage 非零後跑 `q23/q26` focused learner test

## 下一步建議

下一步不要立刻重跑大矩陣，先做最小驗證鏈：

1. 在公司機 WSL 內跑 `p3_6q28_apply_radio_recorder_v2.sh`
2. 重跑一個小型 recorder smoke trace
3. 確認 raw CSV 已出現 `wideband_cqi,itbs`
4. 接著實作 `Layer 2`：
   - 在 `LteFeedbackComputationRealistic.cc` 或 UE feedback send path
     加 `sinr / meanSnr / rsrp` recorder
5. 只有在 `wideband_sinr_db / rsrp_dbm / sinr_db` coverage 變成非零後，
   才值得回 learner 端做 focused onset test

## 目前最重要的判斷

到這一步，我們已經可以更有把握地說：

- 現在差距拉不大的原因，不只是 learner 寫得不夠兇
- 很可能也和 coupled trace 裡只有離散 CQI、缺少真正連續 radio evidence 有關
- 但這件事不能再靠猜
- 必須先把 `SINR / RSRP` recorder 接出來，才能進入下一輪實證
