# P2.6：Decision-context Feature Study

更新日期：2026-08-05

## 研究問題

P2.5 發現 teacher utility 使用 `previous_quality`，最佳 grouping 也依賴
`rb_available`，但 learner 原本看不到這兩項資訊。P2.6 檢查補齊 decision
context 後，同一個 mixed-load learner 是否能改善 ambiguous 場景。

## 實驗設計

- 同一模型混合 light 40 + medium 40 個 training scenarios；
- 各自在 light/medium 20 個 test scenarios 評估；
- ambiguous、Kmax=3、seeds 9/17/23、epochs=12；
- deterministic k-means n_init=10；
- random-balanced sampling、160 pairs/class；
- 不增加 Kmax、seeds 或正式矩陣。

比較四種 inputs：

1. `history_cost`：原控制組；
2. `history_cost_quality`：加入 normalized previous quality；
3. `history_cost_load`：加入 normalized RB budget；
4. `history_cost_context`：同時加入 previous quality 與 RB budget。

## Utility 結果

| Feature mode | Light | Medium |
|---|---:|---:|
| history_cost | 0.81549 | 0.76881 |
| + previous quality | **0.82602** | **0.77569** |
| + load context | 0.81548 | 0.77054 |
| + both contexts | 0.82384 | 0.77384 |

相較原控制組：

- previous quality：light +0.01053、medium +0.00688；
- load only：light -0.00001、medium +0.00173；
- both：light +0.00836、medium +0.00503。

`history_cost_quality` 在 6/6 load/seed slices 都提升：

| Load | Seed | Control | + Previous quality | Delta |
|---|---:|---:|---:|---:|
| light | 9 | 0.776635 | 0.787421 | +0.010786 |
| light | 17 | 0.831292 | 0.841815 | +0.010523 |
| light | 23 | 0.838536 | 0.848831 | +0.010294 |
| medium | 9 | 0.711840 | 0.717822 | +0.005982 |
| medium | 17 | 0.790772 | 0.799730 | +0.008958 |
| medium | 23 | 0.803829 | 0.809515 | +0.005685 |

## 與強 baseline 比較

| Load | + Previous quality | Multi-feature | Resource-cost | Teacher |
|---|---:|---:|---:|---:|
| light | **0.82602** | 0.81467 | 0.81858 | 0.82796 |
| medium | **0.77569** | 0.77400 | 0.77201 | 0.78719 |

在這個 bounded mixed-load study 中，quality-context learner 同時超越兩個強
baseline。Light 距 teacher 只剩 0.00194；medium 距 teacher 仍有 0.01151。

## Teacher imitation

加入 previous quality 後：

- light：pairwise 0.6347 -> 0.6585、ARI 0.2697 -> 0.3112、NMI 0.3469 -> 0.4029；
- medium：pairwise 0.7095 -> 0.7031、ARI 0.3020 -> 0.3332、NMI 0.3371 -> 0.3869。

Medium pairwise accuracy 小幅下降，但 ARI、NMI 與 utility 同時上升，進一步
說明 raw pairwise accuracy 會受群組比例影響，不應單獨作為選模指標。

## 為何 previous quality 有效、load scalar 幫助有限

Previous quality 是每個 user 不同的狀態，而且直接出現在 switching penalty；
補入它是消除不可觀測 label noise。結果穩定提升符合 teacher 機制。

RB budget 則是同一 scenario 內所有 user 共用的 scalar。雖然 MLP 理論上能用它
調整 embedding transformation，但直接把相同數值複製到每個 point，對 k-means
的相對幾何沒有直接辨識力。Load context 仍是必要狀態，但可能要透過
scenario-level conditioning、FiLM/gating 或顯式 K-selection head 才能有效利用。

## P2.6 判定

P2.6 通過。`history_cost_quality` 是目前最強且機制合理的 learner feature 候選，
在 bounded study 中穩定 6/6 提升並首次於 light、medium 平均都超越強 baseline。

暫不覆寫舊正式矩陣或刪除 `history_cost` baseline；先保留兩者以維持研究軌跡。
下一步應用同一小矩陣確認 quality-context 在 aligned 與 heavy 的副作用，或先做
utility-regret supervision。仍不需要擴大 Kmax/seeds。

