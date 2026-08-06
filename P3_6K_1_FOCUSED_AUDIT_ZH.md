# P3.6k-1 Focused Audit on `3|4|5|6 @ gnb_2`

Last updated: 2026-08-06

## 目標

`P3.6k` 已經決定停止投資舊的 `seg_01` plateau family，並切換到新的主目標：

- `3|4|5|6 @ gnb_2`

`P3.6k-1` 的任務是先把這條 family 看懂：

1. 它為什麼是 near-miss
2. 它真正缺的是 cost、quality，還是 temporal 結構
3. 下一個 redesign 應該先推哪一側

## 產物

新增腳本：

- `build_p3_6k1_family_focus.py`

執行：

```powershell
python build_p3_6k1_family_focus.py --bundle-dir p3_6i2_coupled_bundle/bundle --audit-csv p3_6i2_teacher_audit/full_bundle/scenario_teacher_decisions.csv --target-ue-ids "3|4|5|6" --serving-gnb gnb_2 --out-dir p3_6k1_family_focus
```

輸出：

- `p3_6k1_family_focus/summary.txt`
- `p3_6k1_family_focus/family_timeline.csv`
- `p3_6k1_family_focus/family_user_snapshot_metrics.csv`
- `p3_6k1_family_focus/family_user_summary.csv`
- `p3_6k1_family_focus/peak_snapshots.csv`

## 家族概況

### 基本資訊

- family: `3|4|5|6 @ gnb_2`
- time window: `25.8s ~ 29.9s`
- scenario_count: `42`
- teacher positive gain count: `0`

`summary.txt` 顯示：

- `max_teacher_gain_vs_single = 0.0`
- `max_cqi_range = 6.0`
- `max_resource_cost_range = 0.8333333333333335`
- `max_previous_quality_range = 1.0`

這個組合很關鍵，因為它代表：

> 這條 family 不是沒有訊號  
> 而是「明明訊號已經很強，teacher 還是完全不分群」

## Per-user 結構

根據 `family_user_summary.csv`：

### `ue 3`

- `cqi = 12 ~ 15`
- `previous_quality = 2 ~ 2`
- `distance = 94.01 ~ 110.90 m`
- `cost = 3.166667 ~ 3.500000`

### `ue 4`

- `cqi = 12 ~ 15`
- `previous_quality = 2 ~ 2`
- `distance = 124.07 ~ 142.90 m`
- `cost = 3.166667 ~ 3.333333`

### `ue 5`

- `cqi = 9 ~ 14`
- `previous_quality = 2 ~ 2`
- `distance = 140.92 ~ 157.11 m`
- `cost = 3.166667 ~ 4.000000`

### `ue 6`

- `cqi = 13 ~ 14`
- `previous_quality = 1 ~ 2`
- `distance = 158.97 ~ 164.16 m`
- `cost = 3.166667 ~ 3.333333`

## 核心觀察

### 1. `ue 5` 才是後段真正的弱點

這一點和一開始的直覺不完全一樣。

剛看前段時，很容易以為：

- `ue 4` 比較弱，因為它在 `25.8s ~ 26.5s` 的 CQI 只有 `12~13`

但整段看完之後，真正最穩定的 late-window 弱點其實是：

- `ue 5`

在 `29.2s ~ 29.9s`：

- `ue 5` 的 `cqi = 9~10`
- `ue 5` 的 `cost = 4.0`
- 其餘三人幾乎都在 `cost = 3.167`

也就是說，尾端其實已經形成：

- 一個明顯高 cost / 低 CQI 候選者：`ue 5`
- 三個相對穩定的較強者：`ue 3 / ue 4 / ue 6`

### 2. `previous_quality` 幾乎完全靜止

這是目前最重要的診斷。

這條 family 裡：

- `ue 3` 固定在 `2`
- `ue 4` 固定在 `2`
- `ue 5` 固定在 `2`
- `ue 6` 只有 `1 -> 2` 的小變化

而且到最有訊號的尾端：

- `previous_quality_range = 0`

也就是說，當 `cqi_range` 已經到 `5~6`
、`resource_cost_range` 已經到 `0.833333` 時，
teacher 看到的仍然是：

- quality continuity 幾乎沒有差別

所以這條 family 現在很像：

> CQI / cost 已經在喊「可以切」  
> 但 previous-quality 完全沒有幫 teacher 提供 continuity-side 的 split incentive

### 3. temporal signal 是單調變強，不是 flip

這條 family 和 `seg_01` 很不一樣。

`seg_01` 比較像：

- 有局部 temporal flip
- 某些 snapshot 會切、某些不切

但 `3|4|5|6 @ gnb_2` 比較像：

- 從前段到尾段，near-miss 訊號單調變強
- 尤其 `29.2s ~ 29.9s` 最強
- 但 teacher 一路都維持 `[[0,1,2,3]]`

這比較像「單一弱點越來越明顯，但還沒跨過 teacher split threshold」。

## 為什麼 teacher 還是不分

根據目前資料，最合理的解釋是：

1. `ue 5` 雖然後段變弱
2. 但 `previous_quality` 沒有和這個弱化一起產生對齊
3. 其餘三人又維持得太整齊

所以 teacher 看見的不是：

- 一個值得被 isolate 的 continuity-sensitive user

而更像是：

- 一個單點 throughput 弱者，但不足以打破 single-group economics

## P3.6k-1 的結論

### 結論 A

這條 family 的下一步不應該優先做更重的 cost-side 疊加。

原因：

- `ue 5` 在尾段已經有很明顯的 cost disadvantage
- 但 teacher 還是完全不分

這表示單靠 cost-side，很可能重複 `j-2` 那種「只是把人變更慘，卻沒有真正放大 split incentive」的問題。

### 結論 B

這條 family 最值得先推的是：

- **localized previous-quality divergence**

尤其是尾段 `29.2s ~ 29.9s`。

因為目前最缺的不是：

- cost 不夠

而是：

- cost / CQI 訊號沒有被 quality continuity 對齊

### 結論 C

第一個 redesign 最應該瞄準：

- `ue 5` 作為主要弱候選者
- `ue 4` 作為可能的競爭次候選者

也就是說，新 family 的故事不該再複製 `seg_01` 的 `ue 15 vs everyone`，而應該更像：

> 尾段 `ue 5` 漸漸成為主要弱點  
> `ue 4` 在 earlier window 有過較弱跡象  
> 如果再給一點 localized quality offset，可能會形成新的 split threshold

## 下一步建議

正式進入：

### P3.6k-2

方向建議：

- 保持 `3|4|5|6 @ gnb_2` family
- 只針對 `29.2s ~ 29.9s` 尾段做 redesign
- 優先加入 localized previous-quality divergence
- 若要做 cost-side，應該只做很輕微輔助，不該當主力

最合理的第一版設計是：

1. 讓 `ue 5` 的 previous quality 在尾段下降
2. 視需要讓 `ue 4` 保持較高或較穩定 quality
3. 不先動 mobility / family composition

## 一句話結論

`P3.6k-1` 的核心發現是：`3|4|5|6 @ gnb_2` 這條新 family 不是缺 CQI 或 cost，而是缺和尾段弱者 `ue 5` 對齊的 localized previous-quality divergence；所以下一步應該先做 quality-side redesign，而不是直接再加重 cost。 
