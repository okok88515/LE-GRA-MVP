# P3.6e-2 Tighter Budget Sweep 結果

更新日期：2026-08-06

## 這一輪做了什麼

我們沒有重新跑模擬，而是直接使用 `P3.6e-1` 產生的同一份 raw coupled trace：

- `p3_6e_coupled_output/raw_radio.csv`
- `p3_6e_coupled_output/raw_mobility.csv`

然後在 bundle conversion 階段做 tighter `rb_budget_ratio` sweep：

- `0.50`
- `0.40`
- `0.32`

並對每個 budget 各自產生：

- bundle
- coupled-data audit
- teacher-decision audit

總控腳本：

- `run_p3_6e2_budget_sweep.py`

輸出目錄：

- `p3_6e2_budget_sweep/`

## 主要結果

`p3_6e2_budget_sweep/budget_sweep_comparison.csv`

| rb_budget_ratio | full multi-group ratio | full positive gain count | learner-test multi-group ratio |
|---|---:|---:|---:|
| 0.50 | 0.00488 | 0 | 0.0 |
| 0.40 | 0.00000 | 0 | 0.0 |
| 0.32 | 0.02927 | 24 | 0.0 |

## 核心解讀

### 1. 資源壓力確實是關鍵瓶頸

這一輪最重要的收穫是：

- 在 `rb_budget_ratio = 0.32` 時，offline teacher 終於開始出現真正有意義的 split decision

不是只有「剛好切成兩群」，而是：

- `full_multi_group_count = 24`
- `full_multi_group_ratio = 0.02927`
- `full_positive_gain_count = 24`
- `full_positive_gain_ratio = 0.02927`
- `max_teacher_gain_vs_single = 0.03861`

這代表：

- teacher 不只是在浮點數平手時偶然切群
- 而是真的有 `24` 個 snapshots，split grouping 比單群組更好

### 2. 0.40 沒有效，表示存在 decision threshold

`rb_budget_ratio = 0.40` 的結果反而是：

- `full_multi_group_ratio = 0.0`
- `positive_gain_count = 0`

這表示 teacher 的 split preference 不是線性隨 budget 變化，而比較像：

- 到 `0.40` 還不夠痛
- 到 `0.32` 才跨過某個決策門檻

這個 insight 很重要，因為它告訴我們：

- 問題不只是「場景不夠複雜」
- 還包括「系統壓力沒有強到逼出 grouping tradeoff」

### 3. 有效 split 主要出現在 4-user snapshots

`rb_032` 的 `by_user_count.csv` 顯示：

- 4-user snapshots：`149` 個
- 其中 `24` 個會被 teacher 切成多群組
- `multi_group_ratio = 0.1611`

其他 user_count 幾乎都是 0。

這表示：

- 現在真正的 split pressure 主要落在 `4-user` 的中等規模 snapshot
- 不是 UE 越多就一定越會 split
- 而是「4-user + tight budget + high heterogeneity」這個組合最先進入有效區

### 4. 有效 split 與 CQI/quality heterogeneity 有關

在 `rb_032`：

- `cqi_range_bucket = 3+` 的 snapshots 中，`multi_group_ratio = 0.0923`
- `quality_range_bucket = 1` 的 snapshots 中，`multi_group_ratio = 0.3151`

這表示有效 split 並不是純粹靠人數撐出來，而是更常出現在：

- CQI range 較大
- previous quality 不完全一致

的 snapshots 上。

這和我們原本的研究假設一致：

- radio heterogeneity
- QoE-state heterogeneity

都會影響 grouping 決策。

## 代表性案例

`rb_032` 最強的案例反覆出現在：

- `scenario_id = simu5g_00000254` 到 `simu5g_00000268`
- `timestamp ≈ 14.0s ~ 14.7s`
- `serving_gnb = gnb_2`
- `user_count = 4`
- `teacher_group_count = 2`
- `teacher_group_sizes = 3|1`
- `teacher_gain_vs_single = 0.0386085`
- `cqi_range = 6`
- `previous_quality_range = 1`
- `resource_cost_range = 1.1667`

而且這些案例有一個很漂亮的訊號：

- `teacher_rb_utilization = 1.0`
- `single_rb_utilization = 0.5`

也就是說，在 tight budget 下，split grouping 真的讓系統把可用 RB 用得更有效率，
這不是假訊號。

## 目前還沒解掉的事

### 1. Learner test split 仍然是 0

雖然 `full_bundle` 已經開始出現真正的 split gain，
但 `learner_test_split` 還是：

- `multi_group_ratio = 0.0`
- `positive_gain_count = 0`

這表示目前第一輪 trajectory-aware split 剛好挑到了一個較保守的 UE 組合。

### 2. Full bundle 還沒有達到原本 P3.6e 目標 gate

雖然 `rb_032` 已經是目前最好結果，但距離設計目標還有差距：

- `full_multi_group_ratio = 0.02927`，還沒到原本想要的 `>= 0.05`
- `learner_test_split` 仍沒有真正的 split label

所以 P3.6e-2 是成功的，但還不是終點。

## 研究結論

P3.6e-2 已經回答了一個非常重要的問題：

> teacher 為什麼一直不拆群？

答案是：

- 幾何與 overlap 改善後，資料變得更有資訊
- 但真正讓 teacher 開始穩定出現 split gain 的，是更緊的資源壓力
- 而這個壓力門檻大約落在 `rb_budget_ratio = 0.32` 附近，而不是 `0.40`

## 下一步建議

### 最合理的下一步

進 `P3.6e-3`：

- 保留 `P3.6e-1` 幾何與 overlap
- 保留 `rb_budget_ratio = 0.32`
- 加強 deterministic quality controller 的 heterogeneity

目標是：

- 把 `full_multi_group_ratio` 從 `0.029` 再往上推
- 讓 learner-facing split 也開始出現真正的 multi-group teacher labels

### 暫時不建議的事

現在還不建議先回去跑 learner 第二輪，因為：

- 雖然 full bundle 已經有 24 個正 gain snapshots
- 但 learner test split 還是完全單群組

如果現在直接跑 learner，很可能還是看不到真正的 generalization 差異。

## 一句話總結

P3.6e-2 已經證明：
資源壓力是 coupled trace 從 trivial single-group regime 走向真正 split-decision regime 的關鍵門檻；
`rb_budget_ratio = 0.32` 是目前第一個出現實質 teacher gain 的有效區間，但還需要 P3.6e-3 把這些 split decision 進一步擴大並推進到 learner-facing split。
