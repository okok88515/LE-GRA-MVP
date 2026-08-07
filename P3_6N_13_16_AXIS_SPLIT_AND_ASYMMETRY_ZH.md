## P3.6n-13 ~ P3.6n-16：軸向拆解與 weak-side asymmetry 停損結論

### 這一輪在解什麼問題

`n12b` 證明晚段 `27.9s ~ 28.8s` 的 teacher split 還活著，但 learner 仍然完全貼齊 teacher。  
所以這一輪的目標不是再證明「teacher 可以分群」，而是要回答兩個更細的問題：

1. 到底是哪個軸把 late split 殺掉？
2. 如果保住 split，能不能把它推到比目前更難、甚至 3-group 的 regime？

### P3.6n-13：先把壓縮軸拆開

測了兩個方向：

- `n13a_prevq_only`
  - 只壓 `previous_quality`
- `n13b_cqi_only`
  - 只動 CQI / strong-side compression

結果：

- `n13a_prevq_only`
  - late positive `0 / 10`
- `n13b_cqi_only`
  - late positive `10 / 10`

結論：

- 真正先把 late split 殺掉的，不是 CQI 壓縮
- 而是 `previous_quality` 壓縮

### P3.6n-14：再把 previous_quality 軸拆成 weak / strong 兩側

測了兩個方向：

- `n14a_weak_prevq_only`
  - 只把 weak side 的 `previous_quality` 拉高
- `n14b_strong_prevq_only`
  - 只把 strong side 的 `previous_quality` 拉低

結果：

- `n14a_weak_prevq_only`
  - late positive `0 / 10`
- `n14b_strong_prevq_only`
  - late positive `10 / 10`

結論：

- 真正的 kill switch 是：
  - **weak side `previous_quality` 被拉高**
- 反過來說：
  - 單純降低 strong side `previous_quality` 並不會殺掉 split

### P3.6n-15：只在保住 weak-side previous_quality 的前提下，繼續加大 CQI 差異

測了：

- `n15a_cqi_stronger`
- `n15b_cqi_heavy`
- `n15c_cqi_extreme`

共同設定：

- `weak_prevq = 1`
- `strong_prevq = 4`
- 只增加 weak/strong 間的 CQI 幅度

結果：

- 三個版本在 learner-test late window `27.9s ~ 28.8s`
  - 全部 `teacher_group_count = 1`
  - 全部 `teacher_gain_vs_single = 0`
  - late positive `0 / 10`

結論：

- 只靠把 CQI 差異拉更大，救不回 split
- 這代表可行區間不是「CQI 越強越好」的單調線
- 這是一條很窄的 corridor

### P3.6n-16：改試 weak pair 內部不對稱，看能不能推成 3-group

測了：

- `n16a_weak_asym_light`
- `n16b_weak_asym_mid`
- `n16c_weak_asym_strong`

設計想法：

- 保持 `weak_prevq = 1`
- 不再整體加大 CQI
- 改成只讓 weak pair 內部出現不對稱
- 希望把原本 2-group 結構推成 3-group

結果：

- 三個版本的 learner-test late window
  - late positive `0 / 10`
  - `max_teacher_group_count = 1`
- 沒有任何版本出現 `3 groups`

結論：

- 這種「局部數值微調」還是太接近原本 corridor
- 它不但沒有把 regime 推成 3-group
- 還會直接讓 late split 消失

### 額外驗證：保住 split 不等於變成 learner-hard

雖然 `n13b_cqi_only` 保住了 late split，但 focused learner 結果仍然是：

- `Offline teacher = 0.463148622269105`
- `kmeans_embedding = 0.463148622269105`
- `hybrid_membership_kmeans = 0.463148622269105`

意思是：

- teacher 還活著，不代表 learner 變難了
- 目前 surviving split 仍然是 snapshot clustering / hybrid bridge 可以直接解掉的 regime

### 目前最重要的研究結論

這一輪已經把問題切得很清楚：

1. late split 的關鍵生命線是 weak-side `previous_quality`
2. 只做 CQI 幅度 sweep 沒辦法把 gap 拉大
3. 只做 weak-side asymmetry sweep 也推不出 3-group
4. 目前真正的 bottleneck 不再是「如何讓 teacher 分群」
5. 而是「如何做出 teacher 還會分、但簡單 clustering 不再輕鬆解掉的結構型 regime」

### 建議下一步

不要再做同型的局部數值 sweep。下一步應該轉向：

1. 換 source family，而不是一直卡在 `3|4|5|6 @ gnb_2`
2. 直接找自然會出現 3-group 或 bridge-like ambiguity 的 family
3. 或做更結構化的 redesign：
   - 不同 subgroup 的歷史品質階梯
   - 非單調 temporal crossover
   - 讓 teacher split 依賴結構關係，而不是單一 snapshot 軸
