## P3.6q-3：three-group ladder + temporal crossover 原型失敗

### 目的

在 `P3.6q-1` 的 source family mining 之後，我們已經知道：

- 目前 repo 內沒有明顯新的乾淨 positive family
- 下一步必須嘗試更結構化的資料設計

因此這一輪不再做 local numeric sweep，而是直接在
`3|4|5|6 @ gnb_2` 的 `n10` 模板上做一個最小 structural prototype：

- three-subgroup ladder
- late-window temporal crossover

### 設計

新 bundle：

- `build_p3_6q3_three_group_ladder_bundle.py`
- `p3_6q3_three_group_ladder_bundle/`
- `p3_6q3_teacher_audit/`

核心想法：

1. `ue3` 維持 strong anchor
2. `ue4` 保持 persistent weak
3. `ue5` 作為 boundary user
4. `ue6` 作為 upper-mid / boundary user
5. 在 `28.4s` 之後讓 `ue5` / `ue6` 產生 crossover

希望 teacher 會出現：

- `2-group -> 3-group`
- 或至少更複雜的群組切換

### 結果

teacher audit 顯示：

- `full_bundle`
  - `multi_group_count = 30`
  - `positive_gain_count = 30`
  - `max_teacher_group_count = 2`
- 但在真正關心的 late learner-test window `27.9s ~ 28.8s`
  - `multi_group_count = 0`
  - `positive_gain_count = 0`
  - `max_teacher_group_count = 1`

實際 late window 決策為：

- 全部都是 `teacher_group_count = 1`
- 全部都是 `teacher_gain_vs_single = 0`

### 解讀

這個結果很重要，因為它不是單純「又失敗一次」而已。

它說明了：

1. 光是把 target UEs 人工排成 strong / boundary / weak 三層
   - 不足以讓 teacher 自然形成 3-group
2. 就算再加入 boundary crossover
   - 只要整個 family 的 underlying resource interaction 不支持
   - teacher 還是會回到單群
3. 這代表新的 hard regime 不能只靠 target-family 內部手工排布
4. 更可能需要：
   - 真正不同的 raw source family
   - 或更強的 cross-traffic / contention 結構

### 結論

`P3.6q-3` 失敗後，方向更明確了：

- 不要再期待只靠既有 `3|4|5|6 @ gnb_2` family 的手工 ladder 排布，
  就能自然長出 `3-group`
- 下一步應該把重點轉到：
  - 新 raw source family
  - 或能顯式重建 cross-traffic competition 的新資料生成
