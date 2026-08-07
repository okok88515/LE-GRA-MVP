# P3.6q-11: mechanism study on the `q10` six-user transition regime

## 目標

`q10` 已經證明：

- teacher 能在 `1|2|3|4|5|6 @ gnb_2` 上維持更長的 `{ue2, ue6}` dual-weak corridor
- plain `kmeans_embedding` / clustering baselines 追不上
- `membership_order` 與 `hybrid_membership_kmeans` 可以追回 teacher

所以 `q11` 不再擴大資料，而是專心回答：

1. plain `kmeans_embedding` 到底錯在哪裡
2. `membership_order` 與 `hybrid` 是因為哪個機制追回 teacher

## 使用的 artifacts

- `p3_6q10_kmeans_learner/`
- `p3_6q10_membership_order_learner/`
- `p3_6q10_hybrid_learner/`
- `p3_6q10_test_window_candidate_path_comparison.csv`

## 關鍵發現一：plain kmeans 不是「差一點」，而是前半段整段 collapse

從 `p3_6q10_kmeans_learner/teacher_imitation_diagnostics.csv` 可見：

- test index `0 ~ 3`
  - pairwise accuracy = `0.4666666666666667`
  - ARI = `0.0`
  - NMI = `0.0`
  - predicted group count = `1`
- test index `4 ~ 5`
  - pairwise accuracy = `1.0`
  - ARI = `1.0`
  - NMI = `1.0`
  - predicted group count = `2`

意義：

- plain `kmeans_embedding` 不是全段都差
- 它是在 test window 前 4 個 snapshots 直接 collapse 成 single-group
- 到最後 2 個 snapshots 才追上 teacher

這也解釋了為什麼它的平均 utility 只到：

- `LE-GRA MVP (kmeans_embedding)` = `0.6244860398065387`

而不是 teacher 的：

- `Offline teacher` = `0.6457564299182464`

## 關鍵發現二：plain kmeans 的問題從 candidate ranking 就開始了

觀察 `weak_group_prediction_audit.csv` 的 test window：

- teacher candidate 在 `27.7 ~ 28.2` 全部都是：
  - `2|6`

但 plain `kmeans_embedding` 的 predicted top-k 卻是：

- `27.7` = `3|1`
- `27.8` = `3|1`
- `27.9` = `3|5`
- `28.0` = `3|5`
- `28.1` = `3|5`
- `28.2` = `3|1`

也就是說：

- plain kmeans 不是「candidate 對了，只是 grouping 沒切好」
- 它更早就已經把 weak side 看錯
- 它把注意力放在 `ue3` 搭配 `ue1/ue5` 的 decoy path 上

## 關鍵發現三：membership-aware path 在 test window 穩定鎖定真正的 `{ue2,ue6}`

對照 `membership_order` 與 `hybrid_membership_kmeans`：

- `27.7 ~ 28.2` 的 predicted top-k 全部都是：
  - `2|6`

而且兩者的最終 utility 完全相同：

- `membership_order` LE-GRA = `0.6457564299182464`
- `hybrid_membership_kmeans` LE-GRA = `0.6457564299182464`
- 都與 `Offline teacher` 完全一致

這代表：

1. 這次的成功不需要再靠額外的 embedding k-means 修補
2. 真正重要的是 weak-membership ordering 已經把正確的 dual-weak
   candidate `{ue2,ue6}` 穩定抓出來
3. 一旦 candidate path 對了，後面的 split recovery 就足以追回 teacher

## 關鍵發現四：`hybrid` 在這個 regime 上目前幾乎等價於 `membership_order`

在 `q10` 這條 regime：

- `membership_order` = teacher match
- `hybrid_membership_kmeans` = teacher match
- 兩者 test-window candidate path 也相同

因此目前最合理的解讀是：

- `hybrid` 在這條 regime 上沒有再提供額外增益
- 真正的 gain source 是 membership-aware candidate routing
- 不是 embedding clustering 的 refinement

## 研究意義

這份機制分析很重要，因為它把 `q10` 的訊息講得更精確：

不是單純：

- teacher 比 baseline 好

而是：

1. plain snapshot / clustering path 會被 decoy 候選帶走
2. membership-aware path 可以穩定對準真正的 dual-weak candidate
3. 所以這個 regime 的核心價值在於：
   - 它分離了 `candidate discovery`
   - 與 `group recovery`

## 對下一步的建議

最值得做的下一步不是回去換 family，而是留在 `q10` 做兩類延伸：

1. localized supervision study
   - 讓 plain `kmeans_embedding` 也能更穩定抓到 `{ue2,ue6}`
   - 看 train-side supervision 能不能把它從 `0.6245` 推近 teacher

2. robustness / reportable result
   - 固定這條 `q10` regime
   - 做最小版 seeds / window robustness
   - 把它整理成：
     - plain clustering fails
     - membership-aware routing succeeds
     的主結果段落
