# LE-GRA `medium_matrix_results_v2_after_grad_fix` 結果摘要

更新日期：2026-08-05

## 這一輪在回答什麼

這次重跑的重點，不只是再跑一次 `v2`，而是驗證一個更具體的問題：

1. 修正 LE-GRA learner 在 embedding L2 normalization 上的梯度之後，主結果有沒有明顯改變？
2. 改善如果真的存在，它是全面性的，還是只出現在某些場景？
3. 修正後的 learner，是否比 `Multi-feature k-means` 更接近 offline teacher 的 grouping 結構？

這一輪因此是「修正 learner correctness 之後的正式再驗證」，不是單純加大實驗量。

## 主要結果

### 1. 梯度修正確實有幫助，而且幫助不是假的

在 `aligned/light` 與 `aligned/medium` 兩個條件下，LE-GRA 已經超過：

- `CQI k-means`
- `Multi-feature k-means`
- `Resource-cost k-means`

平均 utility 如下：

| Scenario/load | CQI | Resource-cost | Multi-feature | Offline teacher | LE-GRA |
|---|---:|---:|---:|---:|---:|
| aligned/light | 0.8337 | 0.8300 | 0.8349 | **0.8421** | **0.8357** |
| aligned/medium | 0.7905 | 0.7855 | 0.7928 | **0.8059** | **0.7950** |
| aligned/heavy | **0.5928** | 0.5914 | 0.5914 | **0.6211** | 0.5901 |
| ambiguous/light | 0.8089 | **0.8183** | 0.8120 | **0.8280** | 0.8126 |
| ambiguous/medium | **0.7704** | **0.7716** | 0.7700 | **0.7872** | 0.7698 |
| ambiguous/heavy | **0.5793** | 0.5639 | 0.5747 | **0.5964** | 0.5750 |

這代表先前「learner 可能真的有問題」的懷疑是合理的。修掉後，LE-GRA 在部分情境下已經從「略輸 baseline」變成「可以贏過 baseline」。

### 2. 但 learner 還沒有強到可以直接宣稱全面領先

雖然結果變好了，LE-GRA 仍然沒有穩定壓過所有強 baseline：

- 在 `ambiguous/light`，LE-GRA 高於 CQI 與 Multi-feature，但仍低於 `Resource-cost k-means`
- 在 `ambiguous/medium`，LE-GRA 與 CQI / Multi-feature 幾乎持平，但仍略低
- 在 `heavy` 負載下，LE-GRA 仍沒有形成明顯優勢

如果把 18 個 scenario/load/seed 切片一起看，LE-GRA 的勝場數是：

- 對 `CQI k-means`：10 / 18
- 對 `Multi-feature k-means`：11 / 18
- 對 `Resource-cost k-means`：13 / 18
- 對 `Offline teacher`：0 / 18

所以新的結論不是「LE-GRA 已經完全成功」，而是：

> learner 修正確實把方法往前推了一步，但還沒有把研究問題完全解掉。

### 3. Offline teacher 仍然是最強上界

六個 scenario/load 組合中，`Offline teacher` 全部都是 utility 最佳。

這很重要，因為它代表：

1. teacher + DP 這條線是對的
2. 現在的 student 仍然沒有把 teacher 的 grouping 結構完整學到
3. 研究價值仍然成立，因為 learner 還有可進步空間

## Ablation 結論

這一輪 ablation 的整體訊息比上一輪更細緻。

平均 utility：

| Scenario/load | history_only | history_cost | full |
|---|---:|---:|---:|
| aligned/light | 0.8330 | **0.8364** | 0.8321 |
| aligned/medium | 0.7889 | 0.7914 | **0.7930** |
| aligned/heavy | 0.5916 | **0.5929** | 0.5925 |
| ambiguous/light | 0.8069 | 0.8153 | **0.8157** |
| ambiguous/medium | 0.7668 | **0.7699** | 0.7690 |
| ambiguous/heavy | 0.5770 | 0.5770 | **0.5777** |

可以整理成兩句話：

1. `history_only` 幾乎已經可以排除，因為它大致上仍是最弱輸入。
2. 真正值得保留競爭的是 `history_cost` 與 `full`，而且兩者現在非常接近。

也就是說，這輪結果沒有推翻「resource-cost 很重要」這件事，但它也提醒我們：

> 在 learner 修正之後，`full` 不再像上一輪那樣明顯偏弱，代表更多 feature 可能不是問題本身，真正的關鍵是 learner 能不能把它們學好。

## Teacher-imitation diagnostics 結論

這一輪的 diagnostics 讓整個故事更完整。

### LE-GRA 明顯改善的地方

在 `aligned/light`：

- Multi-feature: pairwise 0.6425 / ARI 0.2506 / NMI 0.3443
- LE-GRA: **pairwise 0.6787 / ARI 0.3353 / NMI 0.3831**

在 `aligned/heavy`：

- Multi-feature: 0.9152 / 0.8175 / **0.8383**
- LE-GRA: **0.9175 / 0.8264** / 0.8365

這說明修正後的 learner，至少在 aligned 場景下，更有能力逼近 teacher 的 grouping。

### 仍然卡住的地方

在 ambiguous 場景：

- `ambiguous/light`：LE-GRA 的 ARI 稍高，但 pairwise 與 NMI 仍不占優
- `ambiguous/medium`：LE-GRA 三項都略低於 Multi-feature
- `ambiguous/heavy`：LE-GRA 也仍略低

所以這輪 diagnostics 支持的結論是：

> LE-GRA 的 learner 確實變正確、也變強了一些，但它在真正困難的 ambiguous 場景下，還沒有穩定學到比 hand-crafted feature clustering 更好的 grouping 規則。

## 研究脈絡現在應該怎麼講

如果要把目前研究用一句比較完整的話講清楚，可以這樣說：

> 我們先用 offline teacher + exact DP 建出一個強而可計算的 supervision target，再讓 LE-GRA 學習把使用者映射到適合 grouping 的 embedding 空間。實驗顯示，resource-cost feature 的確很有價值，而修正 learner 梯度後，LE-GRA 已經能在部分 aligned 條件下超越主要 baseline；但在最具研究價值的 ambiguous 場景，learner 仍未穩定超越 hand-crafted feature clustering，因此下一步應聚焦於 learner 設計，而不是盲目擴大矩陣。

## 下一步建議

### 最優先

1. 先把這輪結果當成新的正式基線，不要再引用舊版 `medium_matrix_results_v2` 當主結論。
2. 以 `history_cost` 和 `full` 為主，做 learner-focused 調整，而不是回去糾結 `history_only`。
3. 把重點放在 `ambiguous` 場景，因為那才是 LE-GRA 真正需要證明自己的地方。

### 技術上最值得做的方向

1. 加入 validation-based model selection，而不是固定看最後一個 epoch。
2. 調整 pair sampling / positive-negative 構造方式，讓 supervision 更貼近 teacher grouping。
3. 規劃小規模 learner sweep，例如 epoch、hidden size、margin、learning rate。
4. 如果 NumPy learner 再怎麼修都很有限，再考慮移到 PyTorch。

### 暫時不建議

1. 先不要急著把 `Kmax` 擴到 4 或 5。
2. 先不要再盲目增加 seeds 或 scenario 數量。
3. 先不要把研究重心移到更多 baseline，而忽略 learner 本身。

## 一句話總結

這輪 `after_grad_fix` 的價值，在於它把研究結論從：

> 「LE-GRA 目前還沒證明 learned embedding 值得」

往前推成：

> 「LE-GRA 的 learner 修正後已經開始顯現價值，但真正困難的 ambiguous grouping 問題，還需要更強的 learner 才能站穩。」
