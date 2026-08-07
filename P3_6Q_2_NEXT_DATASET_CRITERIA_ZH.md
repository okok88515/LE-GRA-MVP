## P3.6q-2：下一輪新資料生成 criteria

### 為什麼現在該轉向新資料

根據 `P3.6q-1` 的 source family mining，repo 內現有 family 已經出現很明確的天花板：

- 強 family:
  - `3|4|5|6 @ gnb_2`
  - `0|1|2|3 @ gnb_2`
  - `0|1|2|3|4 @ gnb_2`
  - `0|1|15|2|3|4|5 @ gnb_1`
- 不是已做透，就是已知太容易，或 hard point 太短

所以如果目標是把：

- teacher
- LE-GRA
- multi-feature
- no-group

之間的差距真正拉大，下一輪資料必須不是舊 family 的微調版，而是從生成條件上就重新瞄準「更難的 split 結構」。

### 下一輪資料必須滿足的 4 個條件

#### 1. teacher 不只要分，而且最好要自然出現 3-group 候選

目前整個 repo 的 `scenario_teacher_decisions.csv` 掃描結果裡：

- `teacher_group_count >= 3` 的案例是 `0`

這代表我們現有資料池天生就缺少多群結構。

因此新資料至少要追求其中一種：

- 真正的 `3-group` teacher optimum
- 或明顯的「2-group vs 3-group boundary」

#### 2. 正增益窗要比現在長

目前 hard family 常見問題是：

- positive segment 太短
- 只有 `1 ~ 4` 個 snapshot

這會導致：

- learner train/test 可用訊號太少
- 很難分清楚失敗是 supervision 問題還是 family 太短

下一輪建議目標：

- 至少做出 `8 ~ 12` 個連續 positive snapshots

#### 3. split 不能只靠單一 snapshot 特徵

目前最麻煩的現象是：

- teacher 雖然有分群
- 但只要它的結構還能被單一 snapshot CQI / cost 軸近似
- `kmeans_embedding` 就會直接解掉

因此新資料應該要讓 teacher split 同時依賴：

- temporal crossover
- subgroup-specific history
- 非對稱 weak recovery / degradation
- cross-traffic interaction

而不是只靠：

- 更大 CQI gap
- 或更強弱者對比

#### 4. 必須保留 cross-traffic interaction

前面 `P3.6i` 已經證明：

- 過度乾淨地重設場景
- 很容易把真正有用的 cross-traffic interaction 一起洗掉

所以新資料不能只保留目標 UE。

應該反過來：

- 保留會影響資源競爭與 handover 的旁支參與者
- 再只對少數核心 UE 做精準控制

### 建議的生成方向

#### A. 3-subgroup ladder

設計三層結構，而不是只做 strong / weak 二分：

- strong subgroup
- boundary subgroup
- weak subgroup

目標是讓 teacher 在不同時間點面臨：

- `2-group`
- `3-group`
- 或 `2-group` 但分法不同

#### B. temporal crossover family

不要讓同一個 weak user 全程都弱。

而是設計：

- 一位使用者先弱後回升
- 另一位使用者先穩後掉
- 第三位使用者維持 boundary

讓 teacher 分群依賴的是時間上的相對排序變化。

#### C. history-sensitive decoy

不要只調 `cqi_now`。

應該刻意讓：

- `previous_quality`
- `cqi_t_minus_1 ~ t_minus_4`
- 以及當前 CQI

形成不一致訊號，讓單一 snapshot clustering 不夠用。

#### D. preserve side traffic

新 family 生成時，應該：

- 先鎖定目標 family
- 再保留至少 `2 ~ 4` 個會共同競爭資源的 side users

避免重蹈 `P3.6i` 的「場景變乾淨但訊號消失」。

### 建議的實作順序

1. 先從現有最有結構性的 family 出發做模板：
   - `3|4|5|6 @ gnb_2`
   - 或 `1|2|3|4|5|6 @ gnb_2`
2. 但不要再做同型微調
3. 直接把它改造成：
   - 3-subgroup ladder
   - temporal crossover
   - history-sensitive decoy
4. 每次只做一個最小新 bundle
5. 先看 teacher 是否：
   - 有 `3-group`
   - 或至少在更長窗內出現結構切換
6. 確認 teacher 真的更難後，再進 learner
