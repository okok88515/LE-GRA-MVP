# P2：Hard-negative Pair Sampling

更新日期：2026-08-05

## 研究問題

P1 已排除 k-means 初始化噪音，但 LE-GRA 在 ambiguous/medium 仍未穩定
超越強 baseline。P2 因此直接修改 learner 的 pair sampling：優先訓練
「teacher 判定不同群、但目前 embedding 距離最近」的負樣本。

## 實作

- 保留 `random_balanced` 為正式預設與控制組。
- 新增 `hard_negative` 策略。
- 新增 `--pairs-per-class`，控制每個 scenario update 最多使用多少正、負 pairs。
- 每個 epoch 記錄 selected positive/negative 數、active-negative ratio，以及
  selected negative mean distance。
- main comparison CSV 同步記錄 sampling 策略與訓練 pair 統計。

## Pilot 發現：舊的 160 pair 上限沒有形成有效篩選

24 users 只有 276 個 unordered pairs；在這批 teacher labels 中，每個 scenario
平均只有約 109--125 個 negative pairs。原本每類上限 160 會納入幾乎所有
negative pairs，因此 random 與 hard-negative 的選取集合相同，不能形成有效
對照。P2 正式比較改用每類 64 pairs。這不改變正式預設，CLI 預設仍為 160。

## 實驗設定

- scenario：ambiguous
- load：light、medium
- Kmax：3
- seeds：9、17、23
- train/test：40/20
- epochs：12
- feature：history_cost
- validation fraction：0
- deterministic k-means：n_init=10
- pair budget：64 positive + 64 negative（若該類不足則全取）
- 比較：random_balanced vs hard_negative

## Utility 結果

| Load | Seed | Random 64 | Hard-negative 64 | Delta |
|---|---:|---:|---:|---:|
| light | 9 | 0.778179 | 0.776491 | -0.001688 |
| light | 17 | 0.833311 | 0.831113 | -0.002198 |
| light | 23 | 0.840533 | 0.838449 | -0.002084 |
| medium | 9 | 0.708761 | 0.708520 | -0.000240 |
| medium | 17 | 0.793323 | 0.793372 | +0.000049 |
| medium | 23 | 0.802709 | 0.813203 | +0.010494 |

平均結果：

- light：0.81734 -> 0.81535，delta = -0.00199；
- medium：0.76826 -> 0.77170，delta = +0.00343。

Hard-negative 的 medium 改善主要由 seed 23 帶動，尚不能稱為穩定提升。
而且 hard-negative medium 仍低於 Multi-feature k-means 的 0.7740。

## Teacher imitation 結果

| Load | Metric | Random 64 | Hard-negative 64 | Delta |
|---|---|---:|---:|---:|
| light | Pairwise accuracy | 0.65332 | 0.66274 | +0.00942 |
| light | ARI | 0.29976 | 0.32176 | +0.02200 |
| light | NMI | 0.36278 | 0.38823 | +0.02545 |
| medium | Pairwise accuracy | 0.69481 | 0.72603 | +0.03122 |
| medium | ARI | 0.28011 | 0.31731 | +0.03720 |
| medium | NMI | 0.31781 | 0.33928 | +0.02148 |

Hard-negative 在兩種 load 的三個 partition 指標全部提高，表示 learner 確實
更接近 teacher partition；但 partition imitation 的改善沒有一致轉換成最終
utility。這再次顯示目前 pairwise contrastive objective 與 downstream utility
之間仍有 alignment gap。

## Pair 統計

Hard-negative 相較 random 64：

- active-negative ratio 一致較高；
- selected negative mean distance 一致較低；
- 代表 sampler 按設計聚焦於 embedding 中最容易混淆的 teacher-negative pairs。

例如 medium/seed 23，active-negative ratio 從 0.814 升至 0.923，mean negative
distance 從 0.583 降至 0.446。

## P2 判定

P2 部分通過：hard-negative 的機制與 imitation 改善獲得驗證，但 utility 改善
只出現在 ambiguous/medium 的平均值，且不穩定；light 反而三個 seeds 都小幅
下降。因此不把 hard-negative 設為正式預設，保留為可選實驗策略。

## 建議下一步

優先研究 semi-hard 或 utility-aware weighting，而非增加矩陣規模：

1. semi-hard negatives：不要永遠只取最近的 64 對，混合 hard 與 random，避免
   過度專注局部邊界；
2. 依 teacher grouping 決策的重要性或 utility regret 對 pairs 加權；
3. 特別檢查「imitation 上升但 utility 不升」的 test scenarios，找出錯誤 pair
   對 K 選擇、最差 user CQI 與 resource cost 的影響。

