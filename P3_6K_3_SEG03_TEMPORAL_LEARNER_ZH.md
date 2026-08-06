# P3.6k-3 `seg_03` Focused Temporal Learner 結果

日期：2026-08-06

## 背景

在 `P3.6k-2`，我們成功把新 family：

- `3|4|5|6 @ gnb_2`

推進成一段新的正增益 teacher split 區間：

- `seg_03`
- 時間窗：`29.2s ~ 29.9s`
- teacher split：`[[0,1,3],[2]]`
  - scenario-local index `2` 對應 `ue 5`

這是目前第一個跳出舊 `seg_01` plateau 的成功 family，因此下一步不是再改 teacher，而是先檢查 learner 在這個新 regime 上的表現。

## 實驗設定

命令：

```powershell
python run_p3_6g_temporal_learner.py `
  --bundle-dir p3_6k2_hybrid_bundle/bundle `
  --out-dir p3_6k2_seg03_temporal_learner `
  --focus-ue-ids 3 4 5 6 `
  --train-window-end 29.5 `
  --test-window-start 29.6 `
  --test-window-end 29.9 `
  --max-groups 3 `
  --epochs 12 `
  --seed 9 `
  --min-users 2
```

訓練/測試切分：

- focus family：`3|4|5|6`
- train window：到 `29.5s`
- test window：`29.6s ~ 29.9s`

資料量：

- `background_train_scenarios = 721`
- `focus_train_scenarios = 130`
- `focus_test_scenarios = 4`
- `focus_train_positive_gain_count = 4`
- `focus_test_positive_gain_count = 4`

模型選擇：

- `selected_epoch = 11`
- `selection_validation_loss = 0.0011118897958436505`

## 主要結果

來自 `p3_6k2_seg03_temporal_learner/main_comparison.csv`：

| Method | Utility | Avg groups |
|---|---:|---:|
| No grouping | 0.597184 | 1.0 |
| CQI k-means | 0.635793 | 2.0 |
| Resource-cost k-means | 0.635793 | 2.0 |
| Multi-feature k-means | 0.635793 | 2.0 |
| Offline teacher | 0.635793 | 2.0 |
| LE-GRA MVP | 0.635793 | 2.0 |

## Teacher imitation 結果

來自 `p3_6k2_seg03_temporal_learner/teacher_imitation_diagnostics.csv`：

- `Multi-feature k-means`
  - `pairwise_accuracy = 1.0`
  - `ARI = 1.0`
  - `NMI = 1.0`
- `LE-GRA MVP`
  - `pairwise_accuracy = 1.0`
  - `ARI = 1.0`
  - `NMI = 1.0`

而且四個 test snapshots 全部都一致。

## 解讀

這個結果很重要，因為它同時回答了兩件事。

第一，`P3.6k-2` 做出來的新 family 不是假訊號。因為在 `seg_03` 裡，所有會分群的方法都穩定地優於 `No grouping`，表示 teacher split 的確有真實效益。

第二，這個新 regime 雖然成功讓 teacher「需要分群」，但還沒有成功讓 `LE-GRA` 與 `Multi-feature` 拉開差距。原因是這個 split 規律太乾淨了：`ue 5` 在 late window 的弱勢非常穩定，導致只要是合理的 grouping-aware 方法，都能分到和 teacher 一樣的兩群。

換句話說，`P3.6k-2` 解決的是：

- teacher 為什麼會 split

但還沒有解決：

- 為什麼需要 temporal learner 才能比 hand-crafted multi-feature 更好

## 目前最重要的研究結論

到這一步，研究瓶頸已經比以前更明確：

1. 舊 `seg_01` family 已經證明是 plateau，不值得再做微調。
2. 新 `seg_03` family 證明我們可以在新的 family 上穩定創造正增益 split。
3. 但 `seg_03` 仍然太容易，被 `Multi-feature k-means` 完整追上。

所以接下來不應該只是再追求「更多 split」，而是要找：

- teacher 真的需要 temporal continuity 才能做對決策
- 但 snapshot multi-feature 容易混淆

的 regime。

## 建議下一步

下一步應聚焦在新的 targeted redesign，而不是回頭擴大 matrix：

1. 保留 `3|4|5|6 @ gnb_2` 這類新 family-search 思路。
2. 優先設計「snapshot 上看起來接近，但跨時間趨勢不同」的 family。
3. 讓 teacher split 依賴 temporal continuity，而不是單一時間點就很明顯的弱 user。

最具體的方向是：

- 讓兩個 candidate user 在單 snapshot 的 CQI / cost 很接近
- 但只有其中一個在最近幾步持續惡化，或持續帶著較差 `previous_quality`
- 讓 static multi-feature 容易把兩人視為同類，但 LE-GRA 有機會靠 temporal history 分開

## 對研究敘事的意義

這一步不是失敗，而是把論文故事往前推了一格：

- 我們先證明 teacher split 不是只存在於單一舊 family 的偶然現象
- 接著又證明：只要 split 規律太簡單，手工特徵也能追上 teacher

因此研究的真正價值，不再只是「讓 teacher 分群」，而是找到：

- temporal representation 真正必要
- 而 hand-crafted snapshot clustering 不夠用

的場景。
