# P3.6n-9 ~ P3.6n-10：late pair segment extension on `3|4|5|6 @ gnb_2`

日期：2026-08-07

## 目的

在 `n5` 這條 family 上，我們已經知道：

- `27.9s ~ 28.3s` 有短暫的 teacher-positive late weak pair
- 但 `28.4s` 之後會立刻 collapse 回 single-group

所以這一輪的問題不是「要不要再做 learner tweak」，而是先確認：

1. 這條 family 能不能被拉成更長一點的 teacher-positive late segment
2. 如果能，這個新 segment 是不是會變成 genuinely learner-hard regime

## P3.6n-9：只修 `ue4` cliff，不夠

新增：

- `build_p3_6n9_late_cliff_smoothing_bundle.py`
- `p3_6n9_late_cliff_smoothing_bundle/`
- `p3_6n9_teacher_audit/`
- `p3_6n9_focus_mining/`

設計想法：

- 從 `n5` 出發
- 只處理 `28.4s` 之後 `ue4` 的 rebound cliff
- 輕度壓回 `ue4` / `ue5` 的晚段 user-side state
- 不做像 `n6` 那麼重的 full masking

結果：

- late target window `27.9s ~ 29.9s`
  - positive scenario count 仍然只有 `5 / 21`
  - positive timestamps 仍然只在：
    - `27.9 ~ 28.3`
- 和原本 `n5` 一樣，`28.4s` 之後仍全部回到 single-group

關鍵診斷：

- `n5 @ 28.3s`
  - single-group utility = `0.43093639169248765`
  - late pair split `[[0,3],[1,2]]` utility = `0.43814862226910506`
- `n5 @ 28.4s`
  - single-group utility = `0.43093639169248765`
  - 同一個 pair split utility 直接掉到 `0.2925247290733397`

這代表：

- `28.4s` 的問題不是「只差一點點就能繼續 split」
- 而是 pair split 的 utility basin 本身直接消失
- 所以小幅 cliff smoothing 不足以把這條線救成 trainable segment

## P3.6n-10：更強的 late-state hold 成功把 segment 拉長

新增：

- `build_p3_6n10_late_state_hold_bundle.py`
- `p3_6n10_late_state_hold_bundle/`
- `p3_6n10_teacher_audit/`
- `p3_6n10_focus_mining/`

設計想法：

- 不再做小修
- 直接把 `n5 @ 28.3s` 最後一個 positive snapshot 的 `ue4 / ue5` state
  複製到 `28.4s ~ 28.8s`
- 先回答一個更基本的問題：
  - 這條 family 到底能不能被撐成短正增益 segment

teacher-side 結果：

- late target window `27.9s ~ 29.9s`
  - positive scenario count = `10 / 21`
- positive timestamps 變成：
  - `27.9 ~ 28.8`
- teacher split 在這 10 個 snapshot 上都穩定為：
  - `[[0,3],[1,2]]`

focus mining 結果：

- `positive_segment_count = 1`
- `candidate_temporal_slice_count = 30`
- segment:
  - `25.8s ~ 28.8s`
  - snapshot count = `31`

這代表：

- `n10` 是第一個真正把 `n5` 晚段 pair 結構撐成可訓練短 segment 的版本

## focused learner validation：`n10` 不是新的 learner-hard regime

新增：

- `p3_6n10a_baseline_kmeans/`
- `p3_6n10b_hybrid_bridge/`

protocol：

- bundle:
  - `p3_6n10_late_state_hold_bundle/bundle`
- focus UEs:
  - `3 4 5 6`
- train end:
  - `27.8`
- test:
  - `27.9 ~ 28.8`
- compared:
  - old `kmeans_embedding`
  - `hybrid_membership_kmeans`

結果：

- `Offline teacher = 0.43814862226910506`
- old `kmeans_embedding` LE-GRA = `0.43814862226910506`
- `hybrid_membership_kmeans` LE-GRA = `0.43814862226910506`

也就是說：

- `n10` 的新 segment 雖然成功變長了
- 但它目前不是新的 bridge-needed / learner-hard regime
- 因為連舊 `kmeans_embedding` 都已經直接 match teacher

## 這輪最重要的結論

### 1. `n5` 這條線確實可以被撐成更長的 teacher-positive segment

`n10` 已經證明：

- 不是只有單點或 5 個 snapshot 的短暫現象
- 這條 family 可以被整理成一段可訓練的 late weak-pair segment

### 2. 但目前 `n10` 仍然是 easy / already-solvable

所以 `n10` 的價值不是：

- 「找到新的 learner-hard regime」

而是：

- 「找到一個可控的、可延長的 positive pair segment source」

### 3. 下一步應該從 `n10` 再往 harder 方向推，而不是停在這裡

最合理的下一步不是回頭做更多 learner tweak，而是做第二階段 redesign：

1. 保留 `n10` 已經成功的 `27.9 ~ 28.8` pair segment
2. 再逐步壓低簡單特徵可分性
3. 觀察舊 `kmeans_embedding` 什麼時候先掉下來
4. 如果能做到：
   - teacher 仍 split
   - old bridge / baseline 開始 miss
   那才會是新的 genuinely learner-hard regime

## 建議下一步

建議沿著 `n10` 做 `n11` 類型的 harder redesign：

- 不要破壞 `27.9 ~ 28.8` 的 segment existence
- 只做最小幅度的 separability compression，例如：
  - 逐步縮小 `ue4` / `ue5` 與 `ue3` / `ue6` 的 CQI gap
  - 逐步縮小 `previous_quality` 差異
  - 或在不破壞 split 的前提下增加 decoy similarity

目標不是立刻找到最終答案，而是找出：

- `n10` 從 easy 走向 hard 的真正失敗邊界
