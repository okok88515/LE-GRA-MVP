# End-of-Day Handoff (2026-08-11)

這份交接是給「接下來在家裡繼續接手這個 repo 的自己 / Codex / Claude」。

今天最重要的突破不是再把 learner 微調得更複雜，而是我們終於做出一個
**會穩定拉開方法差距的新 regime**，證明目前的研究主線應該往
`resource-cost / multi-feature` 與「能刻意製造 CQI 失效情境的 benchmark」
前進，而不是再回去做一般性的 LE-GRA tweak sweep。

## 先讀哪些檔案

建議閱讀順序：

1. `END_OF_DAY_HANDOFF_2026-08-11_ZH.md`
2. `SESSION_HANDOFF.md`
3. `project_overview_zh.html`
4. `report_conclusion_zh.html`
5. `run_anti_cqi_hard_regime.py`
6. `le_gra_mvp.py`
7. `anti_cqi_hard_regime_pilot/main_comparison.csv`
8. `anti_cqi_hard_regime_pilot/scenario_summary.csv`
9. `analysis_method_metrics/method_metrics_report_zh.html`

## 今天實際完成了什麼

### 1. 重新整理中文研究主線

已經把中文敘事改成：

- 這個專案的主要價值，不再是硬證明「LE-GRA 是通用最佳解」
- 而是更誠實地轉向：
  - `CQI-only grouping` 太粗
  - `resource-cost` 比純 CQI 更貼近 allocator 真正面對的代價
  - `multi-feature` 則承認 multicast grouping 不只是一個 scalar 可以解決

已更新檔案：

- `project_overview_zh.html`
- `report_conclusion_zh.html`

內容已補上：

- `multi-feature` 到底有哪些 feature
- 為什麼保留這些 feature
- 它們和 `utility / ADR / fairness / switching / imitation metrics` 的關係
- `resource-cost` 的公式、意義、以及它為什麼合理

### 2. 補了一份方法比較圖表報告

新增：

- `build_method_metrics_report.py`
- `analysis_method_metrics/`

這份報告是把現有 focused temporal learner 結果畫成圖，方便快速看：

- `No grouping`
- `CQI k-means`
- `Resource-cost k-means`
- `Multi-feature k-means`
- `Offline teacher`
- `LE-GRA MVP`

那份圖表的重點不是「結果很好」，而是它清楚顯示：

- 在很多既有 regime 上，只要有 grouping-aware 方法，差距其實不大
- 這也是為什麼你一直會感覺「做很久，但方法彼此拉不開」

### 3. 做出新的 `anti_cqi_hard` regime

這是今天最重要的進展。

我在 `le_gra_mvp.py` 裡新增了 `scenario_mode="anti_cqi_hard"`。

這個 regime 的設計核心是：

- 讓使用者的 wideband CQI 看起來很接近
- 讓 `CQI k-means` 很難只靠當前 CQI 分對
- 但在 RB-level profile、歷史趨勢、previous quality、服務代價上，
  不同 family 其實是可分的

具體做法包括：

- 壓窄 `cqi_now` 的動態範圍
- 建立兩種 hidden family：
  - `broadband family`
  - `peaky family`
- 讓 RB profile 形狀不同，但 wideband CQI 仍然相近
- 給兩個 family 相反方向的時間趨勢
- 刻意讓 `previous_quality` 在 family 間有偏移
- 預設把 `rb_budget_ratio` 壓到比較緊的區間

### 4. 做了自動 mining + focused train/test protocol

新增：

- `run_anti_cqi_hard_regime.py`

這個腳本不是單純隨機生 scenario 然後直接跑，而是會先做 audit，再挑出真正有資訊量的 hard case。

現在的 acceptance 邏輯會偏好：

- `teacher_groups >= 2`
- `cqi_span` 小
- `teacher > no-grouping`
- `teacher > CQI`
- `resource-cost` 至少不能比 CQI 更差
- same-CQI 下仍然有可觀察的 `cost std`

也就是說，它找的不是「任意難」的場景，而是：

- **CQI 看不太出來**
- 但 teacher 的確有理由分
- 而 richer feature / cost-based 方法有機會吃到好處

## 今天最重要的結果

來自：

- `anti_cqi_hard_regime_pilot/main_comparison.csv`
- `anti_cqi_hard_regime_pilot/scenario_summary.csv`

pilot 設定：

- train scenarios = `16`
- test scenarios = `8`
- epochs = `3`
- seed = `9`
- `rb_budget_ratio = 0.24`

### 方法比較結果

utility：

- `No grouping = 0.5555`
- `CQI k-means = 0.5632`
- `Resource-cost k-means = 0.5910`
- `Multi-feature k-means = 0.5881`
- `LE-GRA MVP = 0.5980`
- `Offline teacher = 0.6317`

ADR：

- `No grouping = 3000.0`
- `CQI k-means = 3080.2`
- `Resource-cost k-means = 3721.9`
- `Multi-feature k-means = 3453.1`
- `LE-GRA MVP = 3700.0`
- `Offline teacher = 4156.8`

相對關係已經很清楚：

- `No grouping` 最差
- `CQI k-means` 只比 `No grouping` 好一點
- `resource-cost / multi-feature / LE-GRA` 明顯優於 `CQI`
- `Offline teacher` 仍然最好

這是目前很關鍵的訊號，因為它代表：

- 我們終於不再卡在「所有 grouping-aware 方法幾乎一樣好」
- 也重新出現了你之前論文裡那種「比 CQI 更好的 richer method」現象

### 這組結果告訴我們什麼

1. `CQI k-means` 不是沒用，但在 `cqi_span` 很窄時，它很容易失去辨識力
2. `resource-cost` 的提升，證明「服務代價」比「眼前 CQI」更接近真實 bottleneck
3. `multi-feature` 能吃到一部分額外資訊，但目前還不是穩定最好
4. `LE-GRA` 有進步，但目前仍然沒有超過最好的 hand-crafted baseline
5. `Offline teacher` 仍然是上限，表示這條路有真實可追的 gap

## 為什麼這次比前面有進展

因為我們這次終於不是在一個「只要有 grouping 就差不多」的 regime 裡打轉。

之前很多 scenario 的共同問題是：

- allocator 已經很強
- grouping 只要不要太離譜，最終 utility 就差不多
- 所以再怎麼換 learner loss、pair weighting、candidate calibration，
  很多時候都只是在 plateau 上做小修小補

這次 `anti_cqi_hard` 的價值在於：

- 它故意把「CQI 可見資訊」壓低
- 同時保留「代價 / 結構資訊」的可辨識性
- 所以方法間差距終於重新被放大

## 現在最值得做的下一步

### 主線

把 `anti_cqi_hard` 從 pilot 擴成一個更正式的 benchmark。

建議順序：

1. 先固定目前 `anti_cqi_hard` protocol，不要再同時改很多 generator 細節
2. 擴大成較正式版本：
   - 例如 `train=96`
   - `test=32`
   - `epochs=8~12`
3. 觀察以下排序是否穩定：
   - `teacher > LE-GRA / resource-cost / multi-feature > CQI > no-grouping`
4. 如果穩定，再開始看：
   - `LE-GRA` 能不能超過 `resource-cost`
   - `multi-feature` 在哪些 slice 比 `resource-cost` 好

### 不要優先做的事

先不要回去做這些：

- 大量 learner-side 微調 sweep
- 舊 plateau regime 的小改動 replay
- 再做一輪「boundary weighting / candidate BCE / selector tie-break」那種 isolated tweak

原因很簡單：

- 這些路線前面已經證明過，很花時間，但對最終 gap 幫助很有限

## 一句話總結目前狀態

截至 2026-08-11，這個專案最有說服力的成果，已經不再是「LE-GRA 是否是通解」；
而是我們成功證明了：

- `CQI-only grouping` 太粗
- `resource-cost` 與 `multi-feature` 更接近 multicast grouping 的真實難度
- 只要 benchmark 設計得夠好，方法之間的差距是可以被穩定放大的

## 如果回家後要直接接著做

請先做：

1. `git status`
2. 讀：
   - `END_OF_DAY_HANDOFF_2026-08-11_ZH.md`
   - `SESSION_HANDOFF.md`
3. 先看：
   - `anti_cqi_hard_regime_pilot/main_comparison.csv`
   - `anti_cqi_hard_regime_pilot/scenario_summary.csv`
4. 然後把 `anti_cqi_hard` 擴成較正式實驗

### 建議起手命令

```powershell
python .\run_anti_cqi_hard_regime.py `
  --out-dir anti_cqi_hard_regime_v1 `
  --train-scenarios 96 `
  --test-scenarios 32 `
  --epochs 10 `
  --pairs-per-class 160 `
  --validation-fraction 0.15 `
  --seed 9 `
  --rb-budget-ratio 0.24 `
  --max-attempt-multiplier 40 `
  --target-buffer-multiplier 4
```

### 先不要做的事情

不要一開始就：

- 擴大很多 seed matrix
- 重做 generic learner sweep
- 回頭糾結舊的 narrow plateau family

先確認 `anti_cqi_hard` 是否能把 gap 穩定放大，這會比繼續補舊 regime 更有研究價值。
