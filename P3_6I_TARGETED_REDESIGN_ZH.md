# P3.6i Targeted Family Redesign

更新日期：2026-08-06

## 目標

P3.6h-2 已經指出，`rb_028` 下最值得放大的第二個 family 是：

- `1|2|3|4|5|6 @ gnb_2`
- 正增益區間：`27.3s ~ 27.6s`

問題是這段正增益 window 太短，test 只有 2 個 snapshots，難以做更可靠的 learner study。

因此 P3.6i 的目標是：

> 不先改 learner，而是直接修改 coupled scenario，嘗試把這段 family 的空間異質性與 split window 拉長。

## 實作內容

新增檔案：

- `p3_6i_coupled_scenario/targeted_family.rou.xml`
- `p3_6i_coupled_scenario/targeted_family.sumocfg`
- `p3_6i_coupled_scenario/targeted_family.launchd.xml`
- `p3_6i_coupled_scenario/omnetpp.ini`
- `p3_6i_run_targeted_family_coupled.sh`
- `build_p3_6i_coupled_bundle.py`

### 設計原則

這版 redesign 沿用原本的雙 gNB 幾何與 `rb_budget_ratio = 0.28` 研究目標，但把 northbound 車流改成更有結構的速度階梯：

- `sprinter`
- `lead`
- `fast`
- `mid`
- `slow`
- `crawl`
- `anchor`

並對 northbound `0..7` 引入更大的發車間距與更寬的 maxSpeed 梯度，目的是讓：

- 前段 UE 更快靠近 `gnb_2`
- 後段 UE 更慢留在遠端
- 讓同一 serving gNB 內的 CQI / resource-cost dispersion 持續更久

其餘 southbound / westbound / eastbound 交通仍保留原本的四向結構。

### Runtime 修正

P3.6i 執行時碰到 stale `veins_launchd` 佔住預設 port `9999`。因此 run 腳本加上：

- `veins_launchd -k`

讓它在啟動前自動清掉舊 daemon，避免被前一輪 coupled run 卡住。

## 執行結果

P3.6i coupled simulation 成功完成：

- `sim-time-limit = 50s`
- raw radio rows: `1,047,151`
- raw mobility rows: `2,511`

建立 bundle 後：

- `bundle_scenarios = 836`
- `bundle_users = 2475`
- `bundle_rb_rows = 61875`
- `teacher_scenarios = 836`

## 核心結果：這版 redesign 沒有成功

從 `p3_6i_teacher_audit/full_bundle/scenario_teacher_decisions.csv` 做 focused mining 後：

- `positive_segment_count = 0`
- `candidate_temporal_slice_count = 0`

也就是說：

- 這版 P3.6i 沒有把 `1|2|3|4|5|6` 的正增益 split window 拉長
- 更嚴重的是，它把整體 positive split family 直接洗掉了

## 失敗後的診斷

這次失敗不是沒有價值，因為它幫我們排除了「只要拉大 northbound 速度階梯就會自然變好」這條過度簡單的路。

### 1. 我們把 northbound 車群改得太激進了

這版 northbound 發車時間從原本大約 `0.0 ~ 1.4s`，拉成 `0.0 ~ 4.5s`。

結果是：

- 原本會在關鍵時間窗相遇的 UE 組合被拉散
- family overlap 雖然更有梯度，但不一定還在同一個有效高壓 regime 內

### 2. 原本的 informative regime 不只是 northbound 自己的事情

對照原始 `p3_6e` bundle，可觀察到被保留下來的穩定 UE 集合其實是：

- `0,1,2,3,4,5,6,7`
- 再加上少量其他方向的 `15`、`31`

換句話說，原本的 split regime 很可能不是「單一路向自己就能成立」，而是：

- northbound 主群
- 加上少量 cross-traffic / handover / cell overlap 干擾
- 一起構成 resource pressure 與 channel ambiguity

P3.6i 把 northbound 結構重做之後，反而破壞了這種原本剛剛好的交互作用。

### 3. 這不是 learner 問題，而是 scenario-design 問題

這輪從頭到尾還沒碰 learner，本質上是在回答：

> 如果只改 scenario，split regime 會不會更明顯？

目前答案是：

- 會改變，但不保證往更 informative 的方向改
- 過度拉大 spacing 可能直接把 regime 打散

## 目前最值得保留的 insight

P3.6i 提供了一個很關鍵的反例：

> informative split regime 不是單純把速度差拉大、距離拉長就能得到。

更可能需要的是：

- 保留原本的時間重疊
- 只做「溫和」的速度階梯
- 讓異質性增加，但不要破壞原本已經存在的 cross-traffic interaction

## 下一輪應怎麼改

如果做 P3.6i-2，我會採用更保守的 targeted redesign：

1. 保留原本 northbound 的發車時間範圍
   - 不再把 `0..7` 拉到 `4.5s`
   - 盡量維持原始 `0.0 ~ 1.4s` 的重疊結構

2. 只對 `1..6` 做溫和速度梯度
   - 讓高低速差存在
   - 但不要把整個 platoon 打散

3. 保留 `15`、`31` 這類 cross-traffic 的時序
   - 因為它們很可能是原始 regime 的一部分

4. 先追求「恢復正增益 family 並略微拉長」
   - 不要一開始就追求超長 window
   - 先確認 positive snapshots 能從 `4` 增加到 `6~8`

## 目前進度定位

P3.6i 不算成功結果，但算一次有效的 scenario-design iteration：

- implementation 完成
- coupled simulation 成功跑通
- bundle 與 teacher audit 成功重建
- 已確認這版 redesign 會把正增益 split 洗掉

因此現在最合理的下一步，不是回頭懷疑 LE-GRA，而是進入：

- **P3.6i-2：更保守的 targeted redesign**

