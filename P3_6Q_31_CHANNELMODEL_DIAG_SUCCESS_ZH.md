# P3.6q31 Channel-Model Diag Recorder Success

日期：2026-08-10

## 這份文件在講什麼

這一輪的目標，是把 `SIMU5G_RADIO_SCHEMA.md` 中預留但一直為空的連續型
radio 訊號真正接上，包括：

- `sinr_db`
- `wideband_sinr_db`
- `rsrp_dbm`

前面 `q29` / `q30` 都已證明：

- 把 recorder 掛在 `LtePhyEnb::requestFeedback()` 不穩定
- 把 recorder 掛在 `LtePhyUe::handleAirFrame()` 也不穩定
- `raw_radio.csv` 會出來，但 `raw_radio_diag.csv` 完全不出來

因此真正的問題不是 build，而是掛點不在「量測真的被算出來」的源頭。

## 最後成功的關鍵

成功版本改成直接下沉到：

- `simu5g/stack/phy/channelmodel/LteRealisticChannelModel.cc`
- 函式：`LteRealisticChannelModel::getSINR(...)`

原因很簡單：

1. 這個函式一定真的被呼叫
2. 這裡本來就已經在組 per-band `snrVector`
3. 干擾扣除前的 `snrVector` 複本，可以直接當成 per-band `RSRP`
4. 干擾扣除後的 `snrVector`，就是我們要的 per-band `SINR`

也就是說，在這一層 recorder 不需要再另外追 `getRSRP()`，
同一個地方就能同時得到：

- per-band `sinr_db`
- per-band `rsrp_dbm`
- `wideband_sinr_db`

## 成功 patch

新增腳本：

- `p3_6q31_apply_channelmodel_diag_recorder.sh`

用途：

- patch WSL 中安裝好的 Simu5G source
- 重新編譯 `libsimu5g.so`
- 啟用 `LEGRA_RADIO_DIAG_RAW_CSV` sidecar recorder

成功訊號：

- build output 會出現 `P3_6Q31_CHANNELMODEL_DIAG_RECORDER_OK`

## Focused debug 結果

用 `Multiple-UEs` tutorial 做 focused smoke debug 後，結果如下：

- `raw_radio.csv`：成功
- `raw_radio_diag.csv`：成功

行數：

- `raw_radio.csv`：`10020` data rows
- `raw_radio_diag.csv`：`25944` data rows

diag header：

```csv
timestamp_s,ue_node_id,gnb_node_id,band_index,sinr_db,wideband_sinr_db,rsrp_dbm,frame_type,direction
```

## 為什麼 diag row 比 raw row 多

這不是錯誤，而是因為 channel model 會在多種 packet context 下被呼叫。

在 focused debug 中，出現了三種主要組合：

- `frame_type=0, direction=0` -> `DATAPKT, DL`
- `frame_type=2, direction=0` -> `FEEDBACKPKT, DL`
- `frame_type=2, direction=1` -> `FEEDBACKPKT, UL`

其中最重要的發現是：

- `frame_type=2, direction=1` 的 row count 恰好是 `10020`
- 這和 `raw_radio.csv` 的 data row count 完全一致

所以目前最合理的正式對齊規則是：

- 只保留 `FEEDBACKPKT + UL`

## Exporter 已做的收斂

`simu5g_raw_radio_export.py` 的 `_read_diag_csv(...)` 已更新：

- 如果 sidecar 裡有 `frame_type` 和 `direction`
- 會優先只保留：
  - `frame_type == "2"`
  - `direction == "1"`

也就是：

- `FEEDBACKPKT`
- `UL`

若未來 sidecar 沒有這兩個欄位，則 fallback 回舊行為：保留全部。

## 目前意義

這代表 repo 不再只是「schema 上保留了連續型 radio feature」，
而是真的已經有一條可用的 source hook，可以把這些欄位補進 coupled trace。

對研究的直接價值是：

1. 我們終於能測試「CQI 量化不足」是不是當前 learner 卡關的重要原因
2. 可以建立新的 focused feature mode，例如：
   - `history_cost_radio`
   - `full_radio_context`
3. 可以先只在 `q23/q26` 的 earliest-onset regime 做 focused validation，
   不必一開始就擴整個 matrix

## 建議下一步

最合理的下一步順序：

1. 用正式 coupled pipeline 產出一版帶 `sinr/rsrp` 的 trace
2. 檢查 exporter 最終產物中相關欄位是否真的非空
3. 在 learner 端新增最小 radio-aware feature mode
4. 只在 `q23/q26` onset regime 做 focused test

## 不要立刻做的事

- 不要先擴 matrix
- 不要先跑很多 seeds
- 不要先回頭重做 q29/q30 那些外層 hook 微調
- 不要先做大型 learner 結構重寫

現在最重要的是先證明：

- continuous radio signals 能不能真的拉開
  `teacher / LE-GRA / multi-feature / no-group`
  之間的差距
