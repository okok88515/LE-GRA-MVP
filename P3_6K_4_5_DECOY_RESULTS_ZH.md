# P3.6k-4 / P3.6k-5 Decoy 結果

日期：2026-08-06

## 目標

在 `P3.6k-3`，新 family `3|4|5|6 @ gnb_2` 雖然成功產生了穩定的正增益 split，
但 `Multi-feature k-means` 與 `LE-GRA MVP` 都能完美追上 teacher。

因此下一步不是再追求更多 split，而是測試：

- 能不能製造一個「看起來有第二個弱候選人」的 decoy
- 讓 static multi-feature clustering 被誤導
- 但 teacher 仍然只想隔離真正該被隔離的 `ue 5`

## P3.6k-4：history decoy

新增 builder：

- `build_p3_6k4_decoy_history_bundle.py`

輸出：

- `p3_6k4_decoy_history_bundle/`
- `p3_6k4_teacher_audit/`
- `p3_6k4_focus_mining/`
- `p3_6k4_seg03_temporal_learner/`

### 設計

以 `P3.6k-2` 為 base，不改 teacher 直接依賴的 `rb_rates` 與 `previous_quality`，
只在 `seg_03` (`29.2s ~ 29.9s`) 內改 bundle 的 `cqi_history`：

- `ue 4`：做成明顯 recent decline 的 decoy weak-history user
- `ue 5`：做成 mild recovery 的 true weak user

目的不是改 teacher economics，而是讓 raw temporal shape 對 `ue 4` 看起來更可疑。

### Teacher 結果

`seg_03` 完整保留：

- `29.2s ~ 29.9s`
- teacher split 仍為 `[[0,1,3],[2]]`
- `mean_gain_vs_single = 0.038608503577`

也就是說，單改 history 並沒有破壞 teacher regime。

### Learner 結果

來自 `p3_6k4_seg03_temporal_learner/main_comparison.csv`：

| Method | Utility |
|---|---:|
| No grouping | 0.597184 |
| CQI k-means | 0.635793 |
| Resource-cost k-means | 0.635793 |
| Multi-feature k-means | 0.635793 |
| Offline teacher | 0.635793 |
| LE-GRA MVP | 0.635793 |

`teacher_imitation_diagnostics.csv` 顯示：

- `Multi-feature k-means`：`pairwise_accuracy = ARI = NMI = 1.0`
- `LE-GRA MVP`：`pairwise_accuracy = ARI = NMI = 1.0`

### P3.6k-4 結論

這是一個明確的負結果：

- 單靠 temporal history decoy，還不足以讓 `Multi-feature` 掉下來
- 代表目前 `seg_03` 中真正主導 raw feature geometry 的，仍然是 `ue 5` 的 cost / previous-quality 弱勢
- 換句話說，這個 regime 還不是真正的「temporal-only necessary」場景

## P3.6k-5：dual-weak decoy

新增 builder：

- `build_p3_6k5_dualweak_decoy_bundle.py`

輸出：

- `p3_6k5_dualweak_decoy_bundle/`
- `p3_6k5_teacher_audit/`
- `p3_6k5_focus_mining/`

### 設計

以 `P3.6k-4` 為 base，保留 history decoy，再額外給 `ue 4` 一個溫和的次弱訊號：

- 輕度 RB-rate penalty
  - `>=1128 kbps -> 0.95`
  - `>=984 kbps -> 0.92`
  - `else -> 0.97`
- `ue 4 previous_quality -> 1`

設計意圖是：

- 讓 `ue 4` 看起來像 plausible weak candidate
- 但理想上 teacher 仍然應該只隔離更弱的 `ue 5`

### Teacher 結果

這次結果非常重要：

- `seg_03` 完全消失
- `3|4|5|6 @ gnb_2` 在 `29.2s ~ 29.9s` 全部退回單群
- `teacher_groups = [[0,1,2,3]]`
- `teacher_gain_vs_single = 0.0`

也就是說，原本穩定的正增益 split 被第二個弱候選人的加入直接摧毀。

### P3.6k-5 結論

這不是單純的失敗，而是一個很有價值的邊界結果：

1. `seg_03` 能容納一個明確弱 user（`ue 5`）
2. 但還無法容納第二個次弱 candidate（`ue 4`）
3. 一旦 raw feature 空間中出現第二個 plausible weak user，teacher 並不會轉向更豐富的 split
4. 相反地，teacher split incentive 直接消失，整段 collapse 回 single-group

## 到目前為止的整體結論

`P3.6k-4` 與 `P3.6k-5` 合在一起，給了非常清楚的研究訊息：

- 只加 temporal decoy 不夠，因為 raw feature geometry 仍然被真弱 user 主導
- 但如果再加第二個次弱 candidate，這條 family 又太脆弱，會直接失去 split incentive

所以目前真正的瓶頸不是：

- learner 還沒學會

而是：

- 我們目前找到的 `seg_03` regime 還太窄
- 它可以支撐「一個強弱非常清楚的 split」
- 但還不能支撐「兩個 plausible weak candidates 並存，且 teacher 仍穩定偏好其中一個」

## 建議下一步

下一步不建議再沿著 `3|4|5|6 @ gnb_2` 做更細的微調，因為現在已經看到很明確的結構邊界：

- `k-4`：不夠強，拉不開 `Multi-feature`
- `k-5`：一加強就直接把 split 摧毀

更合理的方向是：

1. 換 family source，再找一條本來就有兩個 competing weak candidates 的 near-miss family。
2. 或者重新設計更大的 targeted scenario，不是只修一條 family，而是系統性生成「雙候選弱 user 但 teacher 仍穩定單隔離」的 regime。

研究敘事上，這一步很重要，因為它把問題從：

- 怎麼讓 teacher split

推進到：

- 怎麼找到一個 teacher split 仍穩定，但 static raw-feature clustering 不夠用的 regime
