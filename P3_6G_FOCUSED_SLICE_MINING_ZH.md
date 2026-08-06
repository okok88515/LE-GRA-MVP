# P3.6g Focused Slice Mining

更新日期：2026-08-06

## 這次要回答的問題

P3.6g 已經證明，只要 train 端真的看過正增益 split supervision，LE-GRA 可以在 focused temporal split 上學到 teacher decision。

接下來更實際的問題是：

1. 目前這個 coupled bundle 裡，還有哪些場景真的會讓 teacher 分多群？
2. 除了現在已知的 `0|1|2|3` 之外，還有沒有其他 family 已經接近 split？
3. 如果要複製更多 focused temporal slices，應該優先切哪些時間窗？

## Mining 輸出

新增腳本：

- `find_p3_6g_focus_candidates.py`

輸出目錄：

- `p3_6g_focus_mining/`

其中包含：

- `positive_segments.csv`
- `candidate_temporal_slices.csv`
- `near_miss_families.csv`
- `summary.txt`

## 結論先講

目前的 `p3_6e3_coupled_bundle` 裡，**真的會讓 teacher 產生正增益 split 的 family 只有一個**：

- `ue_ids = 0|1|2|3`
- `serving_gnb = gnb_2`

也就是說，現在不是「我們手上已經有很多不同 split 場景，只是還沒切出來」，而是：

- 目前 bundle 裡只有一個真正成熟的 split family
- 但這個 family 內部其實可以再拆出多個 focused temporal slices

## 真正的 positive segments

`positive_segments.csv` 顯示共有 3 段正增益區間：

1. `seg_01`
   - UE: `0|1|2|3`
   - gNB: `gnb_2`
   - 時間：`14.0s ~ 15.1s`
   - snapshots：`12`
   - `resource_cost_range = 1.1667`
   - `cqi_range = 5 ~ 6`

2. `seg_02`
   - UE: `0|1|2|3`
   - gNB: `gnb_2`
   - 時間：`16.1s ~ 17.0s`
   - snapshots：`10`
   - `resource_cost_range = 1.6667`
   - `cqi_range = 6 ~ 7`

3. `seg_03`
   - UE: `0|1|2|3`
   - gNB: `gnb_2`
   - 時間：`17.6s ~ 17.7s`
   - snapshots：`2`
   - `resource_cost_range = 1.6667`
   - `cqi_range = 6`

這三段都對應到同一個 split 模式：

- `teacher_group_count = 2`
- `teacher_group_sizes = 3|1`
- `teacher_gain_vs_single = 0.038608503576809006`

## 現在就可以用的 focused temporal slices

`candidate_temporal_slices.csv` 自動列出所有 train/test 兩端都保有正增益 case 的 temporal cut。

### 最平衡的 slice

- `seg_01`
- `train_window_end = 14.5s`
- `test_window = 14.6s ~ 15.1s`
- `focus_train_positive_gain_count = 6`
- `focus_test_positive_gain_count = 6`

這個 slice 的優點是 train/test 很對稱，最適合做 protocol 驗證。

### 正增益數量最多的 slice

- `seg_02`
- `train_window_end = 16.1s`
- `test_window = 16.2s ~ 17.0s`
- `focus_train_positive_gain_count = 13`
- `focus_test_positive_gain_count = 9`

這個 slice 的優點是 train 端 supervision 最充足，比較適合測 learner 是否能穩定吃到 split-gain 訊號。

### 已經跑過的跨段 slice

P3.6g 原本跑的是：

- `train_window_end = 15.9s`
- `test_window = 16.0s ~ 18.0s`

它的特性是：

- train 吃到 `seg_01`
- test 吃到 `seg_02 + seg_03`
- train/test 各有 `12` 個正增益 case

這個設計的價值是跨過中間 neutral gap，測試未來時間窗 generalization。

## 哪些 family 最接近 split，但還沒真的 split

`near_miss_families.csv` 是目前最值得注意的 near-miss 排名。

### 第一梯隊：最可能被再加壓推成 split

1. `1|2|3|4|5|6 @ gnb_2`
   - `scenario_count = 18`
   - `user_count = 6`
   - `max_cqi_range = 6`
   - `max_resource_cost_range = 1.1667`
   - 時間：`27.2s ~ 28.9s`

2. `2|3|4|5|6 @ gnb_2`
   - `scenario_count = 20`
   - `user_count = 5`
   - `max_cqi_range = 6`
   - `max_resource_cost_range = 0.8333`
   - 時間：`29.0s ~ 30.9s`

3. `0|1|2|3|4|5 @ gnb_2`
   - `scenario_count = 20`
   - `user_count = 6`
   - `max_cqi_range = 5`
   - `max_resource_cost_range = 0.8333`
   - 時間：`24.0s ~ 26.9s`

4. `3|31|4|5|6 @ gnb_2`
   - `scenario_count = 16`
   - `user_count = 5`
   - `max_cqi_range = 5`
   - `max_resource_cost_range = 0.8333`
   - 時間：`31.0s ~ 32.5s`

### 這代表什麼

這些 near-miss family 已經具備一部分 split 條件：

- 使用者數夠多
- CQI dispersion 不低
- resource-cost dispersion 也開始拉開
- previous quality 也不是完全一致

但它們還差最後一步，teacher 仍然覺得 single-group 的 utility 不輸 split。

## 研究判讀

### 1. 真正有用的 split regime 很稀少

目前 coupled trace 的訊號很明確：

- teacher split 不是常態
- 真正有正增益的 split regime 很稀少，且高度集中

所以如果後面要做 learner 評估，不能只靠「隨便切 train/test」期待剛好抽到有資訊的 supervision。

### 2. `0|1|2|3 @ gnb_2` 是現在唯一成熟的 focused slice family

短期內，如果我們要穩定驗證 learner protocol，最值得反覆使用的還是這個 family。

它至少已經提供三種可用形式：

- `seg_01` 的平衡切法
- `seg_02` 的高 supervision 切法
- 跨段的 `15.9 -> 16.0~18.0` 未來窗切法

### 3. 下一輪 scenario redesign 應該鎖定 near-miss family，不要盲目亂改

如果目標是做出第二個、第三個真正會 split 的 family，最合理的方向不是全面重畫整張場景，而是優先對 near-miss family 所在區段加壓，例如：

- 進一步壓低 `rb_budget_ratio`
- 提高局部同時在線 UE 數
- 增加同區段內的 quality heterogeneity
- 強化 cell-edge / overlap 區的 CQI 落差

## 為什麼目前 teacher 很少 split

「唯一真正有正增益 split 的 family 只有一個」不應該直接解讀成
「LE-GRA 只適用於非常罕見的現實場景」。比較準確的解讀是：

- 目前這份 coupled trace，只有少數時間窗真的進入值得分群的決策 regime
- 在大多數 snapshot 上，teacher 不分群其實是合理決策，而不是資料有問題

目前最可能讓 teacher 不傾向 split 的原因有四個，而且它們通常同時存在：

1. 同一 serving gNB 內的 UE 網路品質差異還不夠大
   - 如果 CQI 太接近，單一群組就能一起服務，分群的額外自由度帶不出明顯效益。
   - 目前唯一正增益 family 的 `cqi_range` 明顯較高，落在 `5~7`。

2. 資源壓力雖然存在，但大部分時間還不夠緊
   - 如果 RB 預算仍然足夠，single-group 可以靠降低少量品質或維持現狀撐住。
   - 先前 sweep 也已經看到：`rb_budget_ratio = 0.40` 幾乎沒有 split，壓到 `0.32` 才開始出現真實正增益 split。

3. resource-cost dispersion 還不夠大
   - teacher 真正在意的不是只有 CQI 差異，而是「同樣升一個品質層，誰會多吃多少資源」。
   - 目前 positive-gain family 的 `resource_cost_range` 約為 `1.17~1.67`，而多數 near-miss family 還停在 `0.83` 或更低。

4. previous quality / switching state 的異質性仍然有限
   - 如果大家前一時刻的品質很接近，single-group 的 switching penalty 通常不大。
   - 若未來要讓 split 更常出現，除了通道差異，影片狀態差異也要更有結構。

因此更合理的研究結論是：

> 目前不是演算法價值很稀有，而是資料中大多數 snapshot 還沒有同時具備足夠大的通道異質性、資源壓力與 quality-state 異質性，所以 teacher 合理地不分群。

這其實反而支持研究方向本身：

- LE-GRA 不需要在每個 snapshot 都硬切群
- 它的價值本來就應該出現在真正需要取捨的高壓異質場景
- 所以下一步不是先懷疑 learner，而是先把這種 informative regime 做得更多、做得更穩定

## 建議下一步

1. 直接把 `seg_01` 平衡 slice 跑成另一個 learner result：
   - `train_window_end = 14.5`
   - `test_window = 14.6 ~ 15.1`

2. 再跑 `seg_02` 高 supervision slice：
   - `train_window_end = 16.1`
   - `test_window = 16.2 ~ 17.0`

3. 如果這兩個 slice 也能讓 LE-GRA 穩定追平 teacher，就代表 P3.6g 的結論不是單一切法偶然成立。

4. 接著再對 near-miss top families 做定向 scenario redesign，目標是把：
   - `1|2|3|4|5|6 @ gnb_2`
   - `2|3|4|5|6 @ gnb_2`
   - `0|1|2|3|4|5 @ gnb_2`

   推成新的正增益 split family。

## 目前的實際限制

我在這台電腦上嘗試直接重跑新的 temporal learner slices，但當前 PowerShell 使用的 `python` 缺少 `numpy`，所以這一步暫時沒有在本機完成。

這不影響 mining 結果本身，因為：

- candidate slices 已經從 teacher audit 直接定量挖出
- near-miss family 也已經排好優先順序

等同一個有 `numpy` 的 Python 環境可用時，就可以直接把上述兩個 slice 補跑。
