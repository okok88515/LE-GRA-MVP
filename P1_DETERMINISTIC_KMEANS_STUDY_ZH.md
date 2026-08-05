# P1：Deterministic Multi-start k-means

更新日期：2026-08-05

## 目的

P1 處理的不是擴大實驗，而是移除 clustering head 的測量噪音：

1. 過去每個 k 只執行一次、使用全域 RNG 的 k-means。
2. 主評估與 teacher-imitation diagnostics 會各自重新分群，因此可能評估到
   不同 partition。
3. diagnostics 沒有 `test_index`，難以可靠做逐 scenario 配對。

## 實作

- k-means 改為固定 seed 的 deterministic implementation。
- 新增可設定的 `n_init`，預設 10。
- 每個 candidate k 執行多次初始化，保留 inertia 最低的 partition。
- 主評估先計算並 cache 每個 method/test scenario 的 grouping。
- diagnostics 重用同一份 teacher、multi-feature 與 LE-GRA grouping。
- diagnostics CSV 新增 `test_index`。
- CLI 新增 `--kmeans-n-init`。

## 小型對照設定

- scenario：ambiguous
- load：light、medium
- Kmax：3
- seeds：9、17、23
- train/test：40/20
- epochs：12
- feature：history_cost
- validation：關閉
- 比較：deterministic `n_init=1` 與 `n_init=10`

原始結果：

- `p1_kmeans_n_init_1/`
- `p1_kmeans_n_init_10/`
- `p1_kmeans_comparison.csv`

## LE-GRA utility

| Load | Seed | n_init=1 | n_init=10 | Delta |
|---|---:|---:|---:|---:|
| light | 9 | 0.773413 | 0.777297 | +0.003884 |
| light | 17 | 0.828855 | 0.829317 | +0.000462 |
| light | 23 | 0.839438 | 0.842289 | +0.002851 |
| medium | 9 | 0.698840 | 0.709757 | +0.010917 |
| medium | 17 | 0.792666 | 0.792599 | -0.000067 |
| medium | 23 | 0.802059 | 0.808257 | +0.006198 |

Multi-start 在 5/6 切片提高 LE-GRA utility：

- light 平均：0.8139 -> 0.8163（+0.0024）
- medium 平均：0.7645 -> 0.7702（+0.0057）

除了 medium/seed=17 幾乎完全持平，其餘切片都改善。Teacher gap 也在
5/6 切片縮小。

## Teacher imitation

LE-GRA 的 `n_init=10 - n_init=1` 平均變化：

| Load | Pairwise | ARI | NMI |
|---|---:|---:|---:|
| light | +0.02011 | +0.04041 | +0.02304 |
| medium | +0.00984 | +0.00078 | -0.01518 |

Light 的 partition agreement 有一致改善。Medium 的 utility 改善沒有對應到
明顯 ARI/NMI 改善，再次說明「更像 teacher partition」與「更高 utility」不是
完全等價。

## 對強 baseline 的影響

Multi-start 也改善 Multi-feature k-means：

- light utility 平均 +0.0053
- medium utility 平均 +0.0044

因此 P1 並沒有自動讓 LE-GRA 全面超越 baseline：

- light：LE-GRA 0.8163，Multi-feature 0.8147；LE-GRA 略高。
- medium：LE-GRA 0.7702，Multi-feature 0.7740；LE-GRA 仍略低。

## P1 判定

P1 通過。

Deterministic multi-start 應保留為標準實驗流程，因為它：

1. 消除全域 RNG 順序造成的不可重現性；
2. 讓 main evaluation 與 diagnostics 使用完全相同的 partition；
3. 在多數切片提高 utility 並縮小 teacher gap；
4. 提供 `test_index`，可做可靠的逐 scenario 診斷。

但 P1 是 clustering reliability improvement，不是 learner 問題的最終解答。
Ambiguous/medium 仍是 LE-GRA 的主要缺口。

## 下一步

進入 P2 learner-focused pair sampling：

1. 加入 hard-negative sampling，優先選目前 embedding 距離最近、但 teacher
   不同組的 pairs。
2. 保留 random/balanced sampling 作對照。
3. 記錄 active-negative ratio 與正負 pair 數。
4. 只跑 ambiguous light/medium、Kmax=3 的小型對照。

在 P2 前仍不擴大 Kmax、seeds 或正式矩陣。

## 白話說明：P1 到底解決什麼

`multi-start` 是對同一份 embedding 用多組初始中心執行 k-means，再選擇
群內平方距離（inertia）最低的結果。`deterministic` 則代表所有初始化都由
固定 seed 產生，因此相同輸入與參數會得到相同 partition。目前正式預設為
`n_init=10`。

P1 的核心問題不是「神經網路是否更強」，而是先排除 clustering head 的
隨機初始化是否讓 LE-GRA 的量測失真。結果顯示，multi-start 讓 LE-GRA 在
6 個 ambiguous light/medium slices 中有 5 個提升，teacher gap 也在 5/6 slices
縮小；但強 baseline 同樣受益。因此 P1 的主要成果是建立較可靠、可重現且
一致的評估流程，而不是宣稱 learner 問題已解決。

最重要的殘留問題仍是 ambiguous/medium：在 `n_init=10` 下，LE-GRA 平均
utility 為 0.7702，Multi-feature k-means 為 0.7740。這也是為何下一步必須
直接改善 learner 的訓練訊號，而不是再靠增加 k-means 初始化次數或擴大矩陣。
