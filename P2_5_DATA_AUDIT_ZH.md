# P2.5：Synthetic Data 與 Teacher Label Audit

更新日期：2026-08-05

## 目的

在繼續修改 learner 或尋找真實資料前，先確認目前 synthetic inputs 是否包含
teacher 決策需要的資訊、train/test 是否合理、teacher labels 是否穩定，以及
不同 partition 的 utility 是否真的有可辨識差距。

本次不訓練 learner，也不擴大矩陣。使用 ambiguous、light/medium、Kmax=3、
seeds 9/17/23、train/test 40/20，共 audit 360 個 scenarios。

## 最重要結論

目前資料可以繼續用於 pipeline 與機制驗證，但 learner input 並不完整，不能
直接把現有結果解讀成模型能力不足。兩個 teacher 決策變數沒有被餵給 learner：

1. `rb_available` / offered load：teacher allocation 與最佳 grouping 直接依賴
   RB budget，但 `history_only`、`history_cost`、`full` 都未包含它。
2. `previous_quality`：teacher utility 使用 previous quality 計算 switching
   penalty；ambiguous generator 還對它加入隨機偏移，但所有 feature modes 都
   沒有包含 previous quality。

這會產生不可消除的 label ambiguity：輸入看起來相同，teacher target 卻可能
因 learner 看不到的狀態而不同。因此下一步應先修正 feature sufficiency，再
繼續設計更複雜的 loss 或大量尋找真實資料。

## 1. Load context 缺失的直接證據

相同 seed 的 light 與 medium 使用完全相同的 user/channel draws，只有
`rb_available` 分別為 50 與 25。因為 load 沒有放入 feature，learner 看到的
history_cost inputs 完全相同，但 teacher partitions 明顯改變：

| Cross-load 指標 | 平均 |
|---|---:|
| Pairwise agreement | 0.7380 |
| ARI | 0.4963 |
| NMI | 0.5787 |
| Teacher K 相同 | 58.3% |
| Partition 完全相同 | 18.3% |

目前每個 load 分開訓練模型，所以單次實驗不會直接混入互相矛盾的 labels；
但模型無法成為真正跨 resource pressure 的 policy，也無法在 deployment 時只靠
現有 features 適應 budget 改變。

## 2. Teacher label 分布

| Load | K=1 | K=2 | K=3 |
|---|---:|---:|---:|
| light | 0 | 27 | 153 |
| medium | 12 | 63 | 105 |

Light 幾乎總是選 K=3；medium 才有較多 K=1/2。這也解釋為何不同 load 的
partition target 不同。

Group sizes 很不平衡：

- light：平均 8.42，範圍 1--22，singleton groups 7.6%；
- medium：平均 9.54，範圍 1--24，singleton groups 11.3%。

因此單純做全域 random pair accuracy 容易被大群與 negative/positive 比例主導。

## 3. Teacher partition 並不總是唯一或重要

| Load | Teacher 對 no-group 平均增益 | Top-1/Top-2 gap | 0.005 內候選數 |
|---|---:|---:|---:|
| light | 0.08893 | 0.00185 | 85.24 / 277 |
| medium | 0.11990 | 0.00325 | 17.26 / 277 |

Light 有 21.1% scenarios 的 top-1/top-2 utility 完全同分；medium 為 17.2%。
Light 平均更有 85 個候選 partition 落在最佳值 0.005 內。這代表 teacher 選出的
單一 partition 常只是許多近似等價解之一；用 hard 0/1 pair labels 強迫 learner
完全模仿該 partition，未必與 downstream utility 一致。

依 channel dispersion 拆開後更明顯：

- high dispersion 才是 grouping gain 的主要來源：light +0.2498、medium +0.3495；
- mid/low dispersion 的 gain 約只有 0.005--0.011；
- 但 light/low 仍有 60/62 scenarios 選 K=3。

也就是某些場景雖然 teacher 選了較多 groups，實際 utility 差異卻非常小。
這會製造對 utility 不重要的 partition label noise。

## 4. Feature 冗餘與 ambiguity

History-cost 共 11 維，但多組 feature 高度相關：

- 相鄰 CQI history correlation 約 0.977--0.978；
- `cqi_t-1` 與 `cqi_now` 約 0.978；
- `cost_q2` 與 `cost_q3` 約 0.987；
- `cost_q4` 與 `cost_q5` 約 0.972。

這不代表 feature 無用，但表示有效資訊維度比 11 低，而且簡單 MLP 可能大量
學到重複訊號。另一方面，同 CQI pairs 每個 scenario 平均約 50 對，其平均
resource-cost distance 只有 0.0122；目前 ambiguous generator 的差異存在，但
在 normalized cost 空間並不算大。

最近鄰與 teacher 同群比例：

- light：0.7067；
- medium：0.7933。

說明 per-user features 有可學訊號，但並不足以唯一決定 teacher partition；
scenario composition、load 與 previous quality 都仍重要。

## 5. Train/test shift

最大 standardized mean difference 約 0.228，出現在 seed 23 的 CQI history；
其餘主要 shift 也多在有限樣本造成的 CQI 平均差異。沒有發現嚴重 train/test
distribution break，但 40/20 的小樣本確實會讓不同 seed 難度有差異。

另外，light 與 medium 的 feature statistics 完全相同並不是好消息，而是因為
load 只改 allocation budget、沒有進入 learner input。

## 6. Synthetic data 是否「夠好」

適合：

- 檢查 allocation、teacher、gradient、clustering 與 logging；
- 比較 feature/loss/sampling 機制；
- 建立 trace-driven 實驗前的快速測試床。

目前不適合：

- 宣稱可泛化到真實 5G vehicular MBS；
- 訓練單一跨 load policy；
- 把 teacher partition 當成唯一 ground truth；
- 根據現有結果判定 neural learner 本身已到極限。

## 優先 TODO

### P0：先修 input sufficiency

1. 將 normalized `rb_available / total_rbs` 加入每位 user 的 feature。
2. 將 normalized `previous_quality` 加入 feature。
3. 以同一個模型混合 light/medium 訓練，做 bounded comparison；只有加入 context
   的模型才應具備跨 load 可識別性。

### P1：修 teacher supervision

4. 記錄多個 near-optimal partitions，或以 utility regret 產生 soft pair weights。
5. 對 top-1/top-2 gap 很小的 scenarios 降低 label 權重。
6. 將 high-dispersion/high-regret scenarios 與近似無差異 scenarios 分開報告。

### P2：再考慮真實資料

7. 尋找真實 CQI/SINR/RSRP 時序與 mobility traces，建立 trace-driven generator。
8. 保留現有 offline optimizer 產生 pseudo-label，不必期待公開資料直接提供最佳
   MBS grouping labels。
9. 用真實 trace 校準 CQI temporal correlation、frequency selectivity、速度分布、
   resource cost 與 load distribution。

## P2.5 判定

Data audit 通過，而且找到了比繼續調 sampling 更優先的問題：缺少 load 與
previous-quality context，以及大量 near-optimal teacher partitions。下一個程式
改動應先補齊這兩個 inputs，做小型跨-load可識別性實驗；暫不擴大 Kmax、seeds
或正式矩陣。

