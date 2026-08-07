## P3.6q-1：source family mining 結論

### 這一輪要回答的問題

在 `P3.6n-13 ~ P3.6n-16` 之後，問題已經不是 teacher 會不會分群，而是：

- 現有 repo 裡，還有沒有其他更值得接手的 source family？
- 或者我們其實已經把目前這批資料能榨出的 family 都看得差不多了？

為了避免繼續靠印象挑 family，這一輪做了兩件事：

1. 新增 `mine_source_family_candidates.py`
2. 產出 `p3_6_source_family_mining/`

這個 miner 不會把所有 audit 直接混在一起累加，而是對每個
`(serving_gnb, ue_ids)` family 保留它在**最佳 source audit**上的表現，避免重複 follow-up
實驗把 ranking 洗歪。

### 正式排名結果

`p3_6_source_family_mining/summary.txt` 的結果是：

1. `3|4|5|6 @ gnb_2`
   - best segment = `42`
   - positive snapshots = `42`
   - max gain = `0.079451741871`
   - source = `p3_6n3_teacher_audit`
2. `0|1|2|3 @ gnb_2`
   - best segment = `24`
   - positive snapshots = `48`
   - max gain = `0.038608503577`
   - source = `p3_6f_teacher_audit`
3. `0|1|2|3|4 @ gnb_2`
   - best segment = `6`
   - positive snapshots = `6`
   - max gain = `0.011900924527`
   - source = `p3_6o4_teacher_audit`
4. `0|1|15|2|3|4|5 @ gnb_1`
   - best segment = `4`
   - positive snapshots = `4`
   - max gain = `0.032424870721`
   - source = `p3_6m4b_teacher_audit`
5. `1|2|3|4|5|6 @ gnb_2`
   - best segment = `2`
   - positive snapshots = `5`
   - max gain = `0.053036980240`
   - source = `p3_6h_pressure_sweep`

其餘 family 更短、更弱，或只剩零星單點。

### 關鍵判讀

#### 1. `3|4|5|6 @ gnb_2`

這就是我們現在已經投入最多的主線。

優點：

- positive segment 最長
- gain 最高
- temporal structure 最豐富

缺點：

- 我們已經驗到很深
- teacher 的 true hard point 仍卡在極窄 corridor
- 同 family 的 local sweep 幾乎已經沒有邊際報酬

結論：

- 它仍然是最強 family
- 但已經不適合再做同型數值微調

#### 2. `0|1|2|3 @ gnb_2`

這條線曾在 `P3.6f / P3.6g` 給過我們很乾淨的 protocol-level 結論：

- 只要 train/test split 對齊
- LE-GRA 可以穩定學到 teacher

但它的研究價值主要已經是：

- supervision protocol 驗證
- 不是 bridge-needed family

結論：

- 已經足夠證明 protocol
- 不適合作為下一個拉大 gap 的主戰場

#### 3. `0|1|2|3|4 @ gnb_2`

這條線在 `o4 ~ o9` 已經被做得很深。

我們已經知道：

- 正增益結構穩定
- 也成功做出過 structure shift
- 甚至出現過 `o8` 的 localized gain recovery

但最後得到的結論是：

- 它比較像 clean bridge case
- 不是可以持續拉開 teacher / LE-GRA / baselines 差距的 family

結論：

- 高價值，但已基本做透

#### 4. `0|1|15|2|3|4|5 @ gnb_1`

這就是現在 `m4b` 的主 family。

優點：

- 真正 learner-hard
- bridge 問題清楚

缺點：

- 原始 positive 支撐很短
- 幾乎所有 minimal learner-side tweak 都已經驗過

結論：

- 它仍然重要
- 但比較適合當 hard benchmark，不適合再期待它自然長出更大正增益窗

#### 5. `1|2|3|4|5|6 @ gnb_2`

這條線曾在 `rb_028` 出現較高 gain，後來也導向 `n5` temporal-swap 系列。

但目前證據顯示：

- 它可以形成短暫且有意義的正增益
- 也可以做出 temporal weak-order change
- 但最後仍然太容易被簡單 clustering 解掉

結論：

- 這條線是有研究價值的 secondary family
- 但目前沒有證據顯示它比 `3|4|5|6` 更有突破機會

### family bank 的補充檢查

我也回頭檢查了 `p3_6m_family_bank_filtered/`。

表面上它的 `rank1` 是：

- `1|2|4|5 @ gnb_2`

但 strict focus mining 結果是：

- `positive_segment_count = 0`
- `candidate_temporal_slice_count = 0`

同樣地：

- `rank4_0|1|15|2|3|4 @ gnb_1`
- `rank5_31|4|5|6|7 @ gnb_2`

也都是：

- `positive_segment_count = 0`

意思是：

- family bank 的部分高分候選比較像 near-miss / dual-candidate ranking artifact
- 不是真正已經成熟到可直接接手成新主線的 positive family

### 最重要結論

這一輪 source family mining 後，可以很明確地下判斷：

1. repo 內真正有穩定正增益訊號的 family 數量非常少
2. 其中最有價值的幾條：
   - 不是已經做透
   - 就是已經證明太容易
   - 或是像 `m4b` 一樣已經成為 hard benchmark，但正增益支撐過短
3. family bank 裡目前沒有新的乾淨 positive 主線被漏掉

### 因此下一步應該怎麼做

下一步不應該是：

- 再對同一條 family 做 local numeric sweep
- 或再從現有 family bank 裡硬挑一條 near-miss 出來試

下一步應該是：

1. 明確轉向新資料生成 / 新 raw source family
2. 生成條件必須針對目前的缺口設計：
   - 需要更自然的 `3-group` 或 bridge-like ambiguity
   - 需要較長的 positive segment
   - 需要讓 split 依賴 temporal / relational structure
   - 不能只靠單一 snapshot CQI 軸就被 `kmeans_embedding` 解掉
