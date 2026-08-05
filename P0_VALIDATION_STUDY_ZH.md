# P0：Validation-based Model Selection 小型研究

更新日期：2026-08-05

## 研究問題

這個 P0 不擴大正式矩陣，只回答一個 learner-focused 問題：

> 使用 held-out training scenarios 選擇最佳 epoch，是否比固定使用訓練結束模型，更穩定改善 ambiguous 場景？

## 實驗設定

- scenario：`ambiguous`
- load：`light`、`medium`
- Kmax：3
- seeds：9、17、23
- train/test：40/20
- epochs：12
- feature：`history_cost`
- 比較：`validation_fraction=0` 與 `validation_fraction=0.2`
- feature ablation：跳過

Validation 版本採 select-then-refit：先以 32/8 fit/validation split 選出
validation contrastive loss 最低的 epoch，再從相同初始權重使用全部 40 個
training scenarios 重訓到選定 epoch，因此不會永久少用 20% 訓練資料。

原始結果：

- `p0_validation_fraction_0/`
- `p0_validation_fraction_20/`
- `p0_validation_comparison.csv`

## Utility 結果

| Load | Seed | No validation | Validation 0.2 | Delta | Selected epoch |
|---|---:|---:|---:|---:|---:|
| light | 9 | 0.772965 | 0.771515 | -0.001451 | 7 |
| light | 17 | 0.829686 | 0.830728 | +0.001042 | 10 |
| light | 23 | 0.838513 | 0.837082 | -0.001431 | 7 |
| medium | 9 | 0.705425 | 0.705365 | -0.000061 | 12 |
| medium | 17 | 0.794881 | 0.794040 | -0.000841 | 9 |
| medium | 23 | 0.802739 | 0.786372 | -0.016367 | 6 |

Validation 版本只在 1/6 個 load/seed 切片提高 utility，未達事先設定的
至少 4/6 勝場門檻。最明顯的退步出現在 `ambiguous/medium/seed=23`。

Teacher gap 也只在 light/seed=17 縮小，其餘五個切片持平或擴大。

## Teacher-imitation 結果

把 120 個 test-scenario partitions 逐一比較，validation 版本相對無
validation 版本的平均變化為：

- pairwise accuracy：+0.00402
- ARI：+0.00483
- NMI：-0.00417

ARI 的微小改善沒有轉化成 utility 改善，而且 NMI 下降。這表示目前使用的
all-pairs validation contrastive loss，與最終 grouping utility／partition
quality 並未充分對齊。

## P0 判定

P0 未通過。

目前沒有證據支持把 `validation_fraction=0.2` 設成標準訓練流程。程式保留
select-then-refit 功能供後續研究，但 CLI 預設值維持 `0.0`，避免改變正式
baseline。

這個結果不是說 validation 永遠無效，而是說：

> 用 contrastive loss 作為 epoch-selection criterion，目前無法可靠預測
> teacher imitation 或最終 QoE utility。

## 下一步

依原定計畫進入 P1：先消除 clustering head 的隨機性。

1. k-means 改為 deterministic multi-start。
2. 同一 scenario/method/k 的 grouping 在 main evaluation 與 diagnostics 間重用。
3. diagnostics 新增 `test_index` 與 selected group count。
4. 完成後只重跑 ambiguous/light、ambiguous/medium 的小型對照。

在 P1 完成前，不擴大 Kmax、seeds 或正式矩陣。
