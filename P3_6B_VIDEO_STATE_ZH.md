# P3.6b Deterministic Video-State Controller

更新日期：2026-08-06

## 目標

P3.6a 已經把 coupled trace 做到有：

- 多 UE snapshot
- 非完全飽和的 CQI
- per-band dispersion
- ambiguous pair
- handover

但還缺最後一塊：

`previous_quality` 仍然是固定控制值 `3`，不是可辯護的 video state。

P3.6b 的目標，就是把這個欄位從「常數」改成「由 coupled radio time series 推導出的自適應 quality state」。

## 為什麼這次先不用原生 app recorder

理想情況下，我們會直接從 Simu5G 的 video / streaming application 錄到：

- representation index
- bitrate
- buffer
- playback / stall state

但目前這條路還沒完整打通。  
如果為了等原生 app recorder 才做下一步，P3.6 會卡很久。

所以這次先採用一個中間但合理的做法：

> 用 coupled radio 已經提供的 per-band achievable rate、RB budget、同 cell 活躍 UE 數量，  
> 建一個 deterministic 的 adaptive-quality controller，輸出可辯護的 `previous_quality`。

這不是「真實 app state recorder」，但已經不是人手寫死的常數。

## 控制器設計

### 輸入

每個 `(timestamp, ue)` snapshot 使用：

- `sum(top rb_available per-band rates)`  
  代表如果這個 UE 在該時刻拿到整個 study RB budget，理論上可支撐的容量
- `active_ues_same_gnb`  
  同一 `(timestamp, serving_gnb)` 下的活躍 UE 數量

### 有效容量估計

控制器不直接用「整個 budget 全給單一 UE」的容量，因為那會過度樂觀。  
本次改用：

`effective_capacity_kbps = achievable_capacity_if_all_budget_assigned / active_ues_same_gnb`

也就是把同 cell 的活躍 UE 數量視為競爭負載，得到較保守、較像 app 端實際可感知的吞吐量。

### 狀態變數

每個 UE 維護：

- `previous_quality`
- `ewma_capacity_kbps`
- `buffer_s`

初始化：

- `initial_quality = 1`
- `initial_buffer_s = 2.0`

### 更新規則

1. 先輸出目前的 `previous_quality`
2. 用當前 `effective_capacity_kbps` 更新 EWMA
3. 根據目前播放 bitrate 與下載能力更新 `buffer_s`
4. 根據 `buffer_s` 選擇較保守或較積極的 capacity margin
5. 算出 `target_quality`
6. 若要升級，最多一次升一階；若風險變高則直接降到 target

這樣做的好處是：

- 不會因為瞬時容量高就立刻跳到最高 quality
- 會保留 startup ramp-up
- 在 cell load 變高時會自然降級
- 在 capacity 足夠且 buffer 穩時才會升級

## 產出檔案

### 更新後的 radio metadata

檔案：`p3_6_coupled_bundle/radio/export_metadata.json`

重要欄位：

- `previous_quality_mode = deterministic_controller`
- `previous_quality_source = deterministic_adaptation_controller_from_radio_capacity_and_cell_load`

### 新增 quality timeline

檔案：`p3_6_coupled_bundle/radio/quality_state.csv`

欄位包含：

- `timestamp_s`
- `ue_id`
- `serving_gnb`
- `active_ues_same_gnb`
- `achievable_kbps_if_all_budget_assigned`
- `effective_capacity_kbps`
- `ewma_capacity_kbps`
- `buffer_s`
- `previous_quality`
- `next_quality`
- `stalled`

這份表就是 P3.6b 最重要的新證據。

## 本次結果

重新 build bundle 並重跑 audit 後：

- `previous_quality_unique_values = 1|2|3|4|5`
- `previous_quality_source = deterministic_adaptation_controller_from_radio_capacity_and_cell_load`
- `quality_switch_count = 42`
- `quality_switch_ratio = 0.016847`

Acceptance gate 結果：

- `measured_previous_quality = PASS`

這代表 P3.6 的六個 gate 已經全部通過。

## 關鍵解讀

### 1. quality state 已經不是常數

先前所有 row 都是固定 `previous_quality = 3`。  
現在 quality 分佈變成：

- 1: 42 rows
- 2: 1507 rows
- 3: 456 rows
- 4: 462 rows
- 5: 36 rows

這說明 controller 確實有把 trace 轉成隨時間演化的狀態，而不是只換一個欄位名稱。

### 2. quality switch 有出現，但不暴衝

- `quality_switch_count = 42`
- `quality_switch_ratio ≈ 1.68%`

這是個不錯的訊號。  
它表示 quality state 不是靜止的，但也沒有因為 controller 太敏感而亂跳。

### 3. 目前 quality 偏中等，不偏最高

分佈以 `2` 為主，其次是 `3` 與 `4`。  
這表示把 cell load 納入 effective capacity 之後，controller 不會因為單 UE 理論容量很高，就永遠選最高 representation。

### 4. startup ramp-up 是可見的

以 `ue_id=0` 為例，前幾個 snapshot 的狀態是：

`1 -> 2 -> 3 -> 4 -> 5`

這很符合「進場後 buffer 逐步建立，再慢慢升 quality」的直覺。

## 仍然要誠實面對的限制

這次 P3.6b 雖然已經讓 acceptance gate 全部通過，但仍有一個重要限制：

> 目前的 `previous_quality` 是由 radio trace 推導出的 deterministic controller，  
> 還不是 simulator 原生 video app 真正吐出的 representation / buffer / playback state。

所以它的研究定位比較準確地說是：

- 已經比固定常數強很多
- 已經足夠當作 coupled trace learner 的 defensible state input
- 但還不是最終版的 app-level ground truth

## 下一步

P3.6 做完之後，合理的下一步有兩條：

1. 用這份已通過 gate 的 coupled bundle，做第一輪 learner real-trace experiment
2. 之後再回頭做更完整的原生 app-state recorder，把 deterministic controller 升級成真正的 application evidence

如果目標是先推進研究主線，建議先做第 1 條。
