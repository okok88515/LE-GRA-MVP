# P3.6q-9: decoy bridge extension on `3|4|5|6 @ gnb_2` did not add hardness

## 設計動機

`q8` 已經證明：

- teacher-side 可以把 `ue4`-isolation 從 `27.1 ~ 27.3` 延長到 `27.1 ~ 27.6`

但也同時證明：

- 這段 bridge 仍然太容易
- `Resource-cost k-means`、`Multi-feature k-means`、`LE-GRA MVP`
  都已經能完全 match teacher

所以 `q9` 的主假設不是再單純延長，而是：

- 保留 `ue4` 當真正 weak candidate
- 讓 `ue5/ue6` 在 snapshot CQI / history 上更像 decoy
- 測試是否能形成：
  - teacher 仍 split `ue4`
  - baseline 卻更容易跟錯

## 實作

新增規格：

- `p3_6q9_decoy_bridge_extension_spec.json`

輸出：

- `p3_6q9_decoy_bridge_extension_bundle/`
- `p3_6q9_teacher_audit/`
- `p3_6q9_focus_mining/`
- `p3_6q9_kmeans_learner/`
- `p3_6q9_hybrid_learner/`

核心做法：

- 延續 `q8` 的前兩段成功結構
- 在 `27.7 ~ 27.9` 及 `28.0 ~ 28.8`：
  - 保留 `ue4` 的低 `previous_quality`
  - 同時把 `ue5` 做成高 previous-quality、較低 snapshot CQI 的 decoy
  - 讓 `ue6` 也保持中等偏弱

## Teacher 結果

`full_bundle` 上 family `3|4|5|6 @ gnb_2` 的 positive snapshots 為：

- `25.8`, `26.2`
  - `[[0,1,3],[2]]`
  - isolate `ue5`
  - gain = `0.09440267226723498`
- `27.1 ~ 27.6`
  - `[[0,2,3],[1]]`
  - isolate `ue4`
  - gain = `0.044402672267235155`

結論：

- 完全沒有超過 `q8`
- `27.7+` 仍然掉回 non-positive / single-group 區間

也就是說：

- decoy 設計沒有把 cliff 再往後推

## Focused learner 結果

設定：

- train end = `27.3`
- test = `27.4 ~ 27.6`
- family = `3|4|5|6`

`kmeans_embedding` 與 `hybrid_membership_kmeans` 的主結果相同：

- `No grouping` = `0.6471841780840183`
- `CQI k-means` = `0.6767859595955085`
- `Resource-cost k-means` = `0.6915868503512534`
- `Multi-feature k-means` = `0.6915868503512534`
- `Offline teacher` = `0.6915868503512534`
- `LE-GRA MVP` = `0.6915868503512534`

另外：

- pairwise accuracy = `1.0`
- ARI = `1.0`
- NMI = `1.0`

## 解讀

`q9` 很重要，因為它幫我們排除了「輕量 decoy」這條路：

1. 它沒有延長 teacher-positive bridge
2. 它也沒有把既有 bridge 變 learner-hard
3. 這代表在這個 family 上，光靠局部 history / CQI decoy 仍不足以：
   - 破壞 resource-cost / multi-feature baseline
   - 或製造真正的 weak-identity ambiguity

## 對下一步的意義

接下來不應再做：

- 同 family 的輕量 decoy 微調
- 單純把 `ue4` 再弱化一點
- 單純把 `ue5/ue6` 再像 decoy 一點

更有價值的方向應該是：

1. 更強的 structure-level conflict
   - 例如讓真正 weak side 與 snapshot 最弱 side 系統性分離
2. 多段切換或更高階 grouping ambiguity
   - 例如 `ue4` 與 `ue5` 在不同 feature space 上各自佔優
3. 新 raw family / 新 source trace
   - 因為目前這個 family 的 local corridor 很可能已接近可榨乾上限
