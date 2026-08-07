# P3.6n-5 Temporal Weak-Order Swap 與 Focused Learner Triage

日期：2026-08-07

## 背景

`P3.6n-3` 已經成功在 `gnb_2` 的 `3|4|5|6` family 上造出新的 teacher-positive regime，
但 learner triage 顯示它仍然是 easy regime：

- teacher 會穩定把 `ue5` 單獨切出去
- 但舊的 `kmeans_embedding` 與 `membership_order` 也都能直接跟上

所以 `P3.6n-5` 的目標不是再造另一個單純的 one-vs-rest split，
而是讓 weak identity 隨時間改變，嘗試製造 temporal ambiguity。

## 設計

基底 bundle：

- `p3_6n3_isolate_ue5_bundle/`

新腳本：

- `build_p3_6n5_temporal_swap_bundle.py`

核心改動：

- family 固定為 `3|4|5|6 @ gnb_2`
- 在 `25.8s ~ 27.8s` 保持 `n3` 的結構：
  - teacher 主要偏好把 `ue5` 單獨切出去
- 從 `27.9s` 開始做 temporal weak-order swap：
  - 顯著削弱 `ue4`
  - 部分恢復 `ue5`
  - 目標是把 late-window 的弱群從 `ue5-only` 轉成 `{ue4, ue5}`

## Teacher 結果

輸出：

- `p3_6n5_teacher_audit/`
- `p3_6n5_focus_mining/`

關鍵觀察：

- `25.8s ~ 27.8s`
  - teacher split：`[[0, 1, 3], [2]]`
  - 對應語意：把 `ue5` 單獨切出去
  - `teacher_gain_vs_single = 0.07945174187052606`
- `27.9s ~ 28.3s`
  - teacher split：`[[0, 3], [1, 2]]`
  - 對應語意：把 `{ue4, ue5}` 作為 weak pair
  - `teacher_gain_vs_single = 0.007212230576617407`
- `28.4s ~ 29.9s`
  - teacher 回到 single-group

因此，`n5` 是第一個在同一個 family 內，
能明確看到 teacher grouping 隨時間改變的 focused regime。

## Focus Mining 結果

- `positive_segment_count = 1`
- `candidate_temporal_slice_count = 25`
- 正向 segment：
  - `25.8s ~ 28.3s`
- 平衡切點大致落在：
  - `27.0s`

但如果研究目標是看 transfer / regime switch，
更有訊息量的切法其實是：

- train end = `27.8`
- test = `27.9 ~ 28.3`

也就是直接把 late-window 的 weak-pair swap 當成 holdout。

## Focused Learner Triage

輸出：

- `p3_6n5a_kmeans_swap_holdout/`
- `p3_6n5b_membership_swap_holdout/`

測試設定：

- bundle：`p3_6n5_temporal_swap_bundle/bundle`
- family：`3|4|5|6 @ gnb_2`
- split：
  - train end = `27.8`
  - test = `27.9 ~ 28.3`

結果：

- No grouping = `0.43093639169248765`
- CQI = `0.438148622269105`
- Resource-cost = `0.438148622269105`
- Multi-feature = `0.438148622269105`
- Offline teacher = `0.438148622269105`
- LE-GRA MVP = `0.438148622269105`

而且：

- `kmeans_embedding` 與 `membership_order` 兩種 grouping mode 結果完全相同

## 診斷

`n5` 的確比 `n3` 更有結構性，因為它首次出現：

- early regime：`ue5-only`
- late regime：`{ue4, ue5}`

但它仍然不是 bridge-needed regime，原因是：

1. late weak pair 雖然存在，但持續時間很短
   - 只有 `27.9s ~ 28.3s`
2. late positive gain 很小
   - 只有 `0.0072`
3. 弱群在簡單特徵上仍然不夠隱蔽
   - baseline 直接就能跟上 teacher

所以 `n5` 比較像：

- teacher dynamics 更豐富
- 但 learner difficulty 還不夠高

而不是新的真正 hard regime。

## 結論

`P3.6n-5` 的價值不在於直接把 gap 拉開，
而在於證明我們已經能主動設計出「teacher grouping 會隨時間改變」的 family。

下一步最合理的方向不是回頭微調 learner，
而是沿著 `n5` 這條線繼續做 scenario redesign：

- 把 late weak-pair window 拉長
- 把 late positive gain 拉高
- 同時避免讓弱群在單純 CQI / distance / previous-quality 上過度顯眼

目標是把它從：

- structurally interesting but easy

推進成：

- structurally interesting and bridge-needed
