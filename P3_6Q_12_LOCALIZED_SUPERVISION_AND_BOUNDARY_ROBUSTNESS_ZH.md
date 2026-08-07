# P3.6q-12: localized supervision can recover `q10`, but boundary-shift robustness is still weak

## 背景

`q10` 與 `q11` 已經建立三件事：

1. `1|2|3|4|5|6 @ gnb_2` 的 `27.7 ~ 28.2` 是真正 teacher-positive 的 dual-weak corridor。
2. plain `kmeans_embedding` 會走錯 weak-candidate path，追到 `3|1 / 3|5` 這條 decoy。
3. `membership_order` 與 `hybrid_membership_kmeans` 都能穩定走回真正的 `{ue2, ue6}` 路徑。

這一輪要回答的問題是：

- plain `kmeans_embedding` 可不可以靠 train-side localized supervision 被拉回 teacher path？
- 如果可以，這個修復是局部記住固定窗口，還是真的對同一條 transition 有穩定 transfer？

## 本輪實驗

### 實驗 1：candidate BCE only

Artifacts:

- `p3_6q10_kmeans_candidate_bce/`

設定：

- `grouping_mode = kmeans_embedding`
- `candidate_membership_weight = 4.0`
- `candidate_top_k = 2`
- `candidate_secondary_scale = 4.0`

結果：

- `LE-GRA MVP = 0.6244860398065387`
- 沒有優於原本 plain `kmeans_embedding`

解讀：

- 只靠 candidate-membership BCE，還不足以把模型從 decoy candidate path 拉回 `{ue2, ue6}`。

### 實驗 2：candidate BCE + teacher-boundary pairs

Artifacts:

- `p3_6q10_kmeans_candidate_boundary/`

額外設定：

- `pair_sampling = teacher_boundary`
- `supervision_weight_mode = teacher_candidate_boundary`

結果：

- `LE-GRA MVP = 0.6244860398065387`
- 仍然沒有改善

解讀：

- 即使加入 boundary-aware positive/negative pair construction，
  沒有更明確的 localized frontier pressure，模型仍然停在錯誤路徑。

### 實驗 3：candidate BCE + teacher-boundary pairs + frontier contrast

Artifacts:

- `p3_6q10_kmeans_candidate_boundary_frontier/`

額外設定：

- `frontier_contrast_weight = 6.0`
- `frontier_negative_top_k = 2`
- `frontier_margin = 0.25`

結果：

- `Offline teacher = 0.6457564299182464`
- `LE-GRA MVP = 0.6457564299182464`

而且這不只是 aggregate utility 追上而已。

從：

- `p3_6q10_kmeans_candidate_boundary_frontier/weak_group_prediction_audit.csv`
- `p3_6q10_kmeans_candidate_boundary_frontier/teacher_imitation_diagnostics.csv`

可見：

- `27.7 ~ 28.2` 六個 test snapshot 的 predicted top-k 全部都是 `2|6`
- 六個 test snapshot 的 pairwise / ARI / NMI 全部都是 `1.0`

解讀：

- 真正推動 plain `kmeans_embedding` recover 的，不是單一 candidate BCE，也不是單一 boundary pair。
- 關鍵是三個 localized hook 的聯合作用：
  - boundary-aware replay / pair sampling
  - candidate-conditioned weak-group supervision
  - frontier hard-negative contrast

這是 `q10` 目前最重要的新突破。

## 小型 robustness check：boundary 往前挪一格後會怎樣？

為了確認這不是只記住原本 `27.7 ~ 28.2` 的固定 6 點，
又做了同設定的 boundary-shift 驗證：

Artifacts:

- `p3_6q10_kmeans_candidate_boundary_frontier_275/`

設定：

- `train_window_end = 27.5`
- `test_window_start = 27.6`
- `test_window_end = 28.2`

結果：

- `Offline teacher = 0.6368533564947124`
- `LE-GRA MVP = 0.6186215935418201`
- teacher gap = `-0.0182317629528923`

更細看 diagnostics：

- `27.6`：LE-GRA 完全 match teacher
- `27.7 ~ 28.0`：LE-GRA collapse 成 single-group
- `28.1 ~ 28.2`：LE-GRA 又恢復成 teacher split

從 `weak_group_prediction_audit.csv` 看，這一點很關鍵：

- candidate path 並沒有掉
- `27.6 ~ 28.2` 七個 test snapshot 的 predicted top-k 全部還是 `2|6`

所以這次失敗不是 candidate discovery 壞掉，而是：

- 雖然模型知道真正 weak pair 是 `{ue2, ue6}`
- 但把這個 candidate 轉成穩定 final split 的 grouping decision 仍然不夠穩

## 結論

這輪結論要分成兩層：

### 結論 A：localized supervision 真的有效

`q10` 已經首次證明：

- plain `kmeans_embedding` 並非一定卡死在 decoy 路徑
- 只要 supervision 同時約束：
  - weak candidate
  - boundary pairs
  - frontier hard negatives
- 它可以完整 recover 到 teacher utility

這代表 learner-side 修復不是完全沒希望。

### 結論 B：但目前修復仍偏局部，還沒有 boundary-shift robustness

當 train/test 邊界從：

- train `<= 27.6`, test `27.7 ~ 28.2`

改成：

- train `<= 27.5`, test `27.6 ~ 28.2`

同一套 supervision 組合就不再穩定。

因此目前最準確的判斷是：

- candidate path recovery 已經做到了
- final grouping transfer 還沒有穩定做到

## 對下一步的建議

最值得做的不是再回去 sweep 小權重，而是直接針對
`candidate is right but grouping still collapses` 這個新瓶頸設計下一步：

1. group-construction stabilization
   - 在 `{ue2, ue6}` candidate 已正確的前提下，
     增加對 final two-group realization 的 localized structural supervision
   - 重點不是再教它「誰是 weak」，而是教它「拿到 weak candidate 後不要退回 single-group」

2. boundary-neighborhood replay
   - 把 `27.6 ~ 28.0` 這種 boundary-shift 區域做成更密集的 replay/support slice
   - 目標是讓模型學到 transition neighborhood，而不是只記住單一 test window

3. report framing
   - `q10` 可以作為很好的故事線：
     - plain clustering fails
     - membership-aware routing succeeds
     - localized joint supervision can recover the exact window
     - but robustness still reveals the remaining grouping-transfer gap

這樣報告會比單純說「成功了」更有研究價值，因為它把成功條件與尚未解決的 gap 都講清楚了。
