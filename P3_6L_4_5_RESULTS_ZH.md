# P3.6l-4 / P3.6l-5 結果

日期：2026-08-06

## P3.6l-4：primary weak + light decoy

新增 builder：

- `build_p3_6l4_primary_weak_bundle.py`

設計目標：

- 保留 `1|2|4|5 @ gnb_2` 的雙候選結構
- `ue 4` 當 primary weak
- `ue 2` 只做 light temporal decoy

與 `l-3` 相比，這版刻意把 `ue 2` 的直接 cost penalty 大幅降低，只保留較弱的 decoy 訊號。

### 重要結果

teacher 在 `23.7s ~ 23.9s` 確實不再維持單群，而是開始 split：

- `teacher_groups = [[0,3],[1,2]]`
- 對應原始 UE 為：
  - `{ue 1, ue 5}`
  - `{ue 2, ue 4}`

但關鍵問題是：

- `teacher_gain_vs_single ≈ 0`

也就是說，這是一個「零增益 split」：

- teacher 願意分群
- 但分群沒有真正比單群帶來更高 utility

### 解讀

`l-4` 是比 `l-3` 更接近目標的一步，因為：

1. `l-3` 完全 split 不出來
2. `l-4` 已經 split 出來
3. 只是還沒有跨過 `gain > 0` 這條線

這證明：

- `1|2|4|5` 這條 family source 是有潛力的
- 現在差的是如何把 split 從「結構存在」推成「效益存在」

## P3.6l-5：push toward positive gain

新增 builder：

- `build_p3_6l5_positive_gain_bundle.py`

設計目標：

- 保留 `l-4` 已經出現的 split 結構
- 再加深 `ue 4` 的 primary weakness
- 同時把 `ue 1 / ue 5` 的 `previous_quality` 拉高到 `3`
- 希望 split 不只存在，還能比單群更有 utility

### 重要結果

結果沒有往正增益前進，反而回退：

- `1|2|4|5 @ gnb_2` 在 `23.0s ~ 23.9s` 全部回到 single-group
- `teacher_groups = [[0,1,2,3]]`
- `teacher_gain_vs_single = 0`

而且後段 utility 被拉高到：

- `0.6471841780840183`

這說明什麼？

- 當我們把 strong pair 的 QoE continuity 拉得更高時
- teacher 更傾向用單群就滿足整體效益
- 原本 `l-4` 那個臨界 split incentive 反而被吃掉了

## 合併解讀

`l-4` 與 `l-5` 合起來，給了一個很清楚的邊界：

1. `l-4` 證明這條 family 已經能出現 split 結構
2. 但這個 split 還只是 tie-utility，不是真正 positive-gain
3. `l-5` 證明不能單純靠把 strong pair QoE 拉高，因為那會把 split incentive 直接消滅

也就是說，現在真正該調的不是 strong pair，而是：

- 如何只讓 `ue 4` 的被隔離價值變高
- 但又不要讓整體單群方案變得更舒服

## 建議下一步

如果接著做 `P3.6l-6`，最合理的方向會是：

1. 保留 `l-4` 的 `previous_quality` 設計，不要再把 `ue 1 / ue 5` 拉到 `3`
2. 只在 `ue 4` 身上加更局部的 cost / CQI weakness
3. `ue 2` 維持 very light decoy，不要再提高它的直接弱化
4. 目標是把 `[[ue 1, ue 5], [ue 2, ue 4]]` 從 tie-utility 推成小幅正增益

一句話總結：

`l-4` 是第一個讓雙候選 family 真正 split 的版本；`l-5` 則告訴我們，想把 split 變成正增益，不能靠強化 strong pair，而要更精準地增加 primary weak user 的 isolation value。 
