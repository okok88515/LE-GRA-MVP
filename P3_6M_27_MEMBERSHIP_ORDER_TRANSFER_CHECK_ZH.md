# P3.6m-27：`membership_order` focused transfer check on `m4b`

日期：2026-08-07

## 這一步要回答什麼

`P3.6m-26` 已經出現一個很關鍵的突破：

- localized hard negatives + `membership_order`
- 在 `m4b` 主 holdout `43.7 ~ 43.9`
- 讓 `LE-GRA` 追平 teacher

但那還可能被質疑成：

- 只是 3 個時間點平均後剛好追平
- 或者只對其中 1 個點有效

所以這一步做的事情很直接：

- 保持同一套訓練
- 保持同一個 focused regime
- 只把測試切成單點
- 看 `43.7`、`43.8`、`43.9` 是否各自都成立

## 固定條件

全部維持 `P3.6m-26` 的 localized hard-negative 設定：

- bundle：`p3_6m4b_threshold_nudge_bundle/bundle`
- family：`0|1|15|2|3|4|5 @ gnb_1`
- train end：`43.6`
- `joint_supervision_mode = m4b_localized_hard_negative_v1`
- `grouping_mode = membership_order`
- `restart_seeds = 7 9 11`
- `background_train_limit = 150`

## 三個 focused single-point checks

輸出：

- `p3_6m27a_m4b_localized_membership_437_only/`
- `p3_6m27b_m4b_localized_membership_438_only/`
- `p3_6m27c_m4b_localized_membership_439_only/`

分別對應：

- `43.7 only`
- `43.8 only`
- `43.9 only`

## 結果

三個 single-point run 的主結果一致：

- `LE-GRA = teacher`

也就是說，在每一個單點上：

- `LE-GRA MVP = 0.579609048805`
- `Offline teacher = 0.579609048805`

而 baseline 仍然是：

- `CQI = 0.579083105194`

## 這一步的意義

### 1. 這不是三點平均後的假象

如果只有平均值追平，還可能是：

- 某個點好、某個點差，剛好平均起來一樣

但現在三個點各自都追平，表示：

- `membership_order` 的成功不是平均效應偽裝出來的

### 2. 這也不是只靠一個 easiest point 撐起來

現在三個點都成立，表示：

- 成功覆蓋了整個主 holdout 區段
- 不是只對 `43.8` 或 `43.9` 單點巧合有效

### 3. `m4b` 上的 bridge 結論已經更穩

到這一步為止，我們已經可以把結論講得比 `P3.6m-26` 更強：

- localized hard negatives 修正了 weak frontier
- `membership_order` 成功把這個 frontier 轉成最終 grouping
- 而且這件事在 `43.7 / 43.8 / 43.9` 三個點上 individually 都成立

## 目前最合理的下一步

接下來最值得做的，不是再回頭懷疑這個結果，而是：

1. 把 `membership_order` 視為正式 bridge candidate
2. 去測：
   - 這個 bridge 能不能 transfer 到別的 focused regime
   - 還是只對 `m4b` 這一條有效
3. 若要保留 embedding path，再研究 hybrid bridge

## 一句話總結

`P3.6m-27` 證明了：

- `membership_order` 在 `m4b` 上追平 teacher
- 不是三點平均後的巧合
- 而是在 `43.7`、`43.8`、`43.9` 三個 single-point holdout 上 individually 都成立。
