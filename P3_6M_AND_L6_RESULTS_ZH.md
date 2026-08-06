# P3.6m 與 P3.6l-6 結果

日期：2026-08-06

## P3.6m 的核心決策

在 `P3.6l-5` 之後，研究方向正式進入 `P3.6m`：

- 不再延續 `1|2|4|5 @ gnb_2` 的粗暴全窗強化
- 改成先重新審視 family source 與 plateau 邊界
- 再做更局部的 late-window gain push

這個階段最重要的認知更新是：

- `1|2|4|5` 確實比 `3|4|5|6` 更適合做 dual-candidate story
- 但 `l-4` 之後，這條 family 也開始顯示出自己的 narrow plateau

## P3.6l-6：late-window gain push

新增 builder：

- `build_p3_6l6_late_window_gain_bundle.py`

輸出：

- `p3_6l6_late_window_gain_bundle/`
- `p3_6l6_teacher_audit/`
- `p3_6l6_focus_mining/`

### 設計

`l-6` 不再像 `l-5` 那樣改整段 family，而是直接以 `l-4` 為 base：

- 只鎖定 `23.7s ~ 23.9s`
- 只改 `ue 4`
- 目標是保留 `l-4` 已經出現的 split 結構
- 同時把 `ue 4` 的 isolation value 再往上推一點

修改內容：

- `ue 4` late-window RB-rate penalty 更強
- `ue 4` late-window history 再往下壓
- 其他 users 與其他時間點都維持 `l-4`

這是一個非常乾淨的局部 intervention：

- `target_scenarios = 3`
- `bundle_rb_rates.csv_modified = 75`
- `previous_quality_modified_rows = 3`
- `history_modified_rows = 3`

## P3.6l-6 結果

結果很明確：

- `1|2|4|5 @ gnb_2`
- 在 `23.7s ~ 23.9s`
- 再次回到 single-group

teacher decision：

- `teacher_groups = [[0,1,2,3]]`
- `teacher_gain_vs_single = 0`

也就是說，`l-6` 沒有把 `l-4` 的 tie-utility split 推成正增益 split；
相反地，它把 split 結構直接消掉了。

## 與前面版本的對照

目前這條 family 的路徑很清楚：

1. `l-3`
   - 雙候選 family source 建立成功
   - 但 teacher 完全不 split
2. `l-4`
   - 第一次成功讓 teacher 出現 split 結構
   - 但 `gain = 0`
3. `l-5`
   - 嘗試靠提高 strong pair continuity 追正增益
   - 結果 collapse 回單群
4. `l-6`
   - 改成只在 late split window 強化 `ue 4`
   - 仍然 collapse 回單群

## 研究意義

`l-6` 是一個非常有價值的負結果，因為它排除了另一條可能的錯覺：

- 問題不是我們改太大一段 family
- 因為就算只在 `l-4` 的 split window 做很局部的加壓
- split incentive 仍然會消失

這說明：

- `1|2|4|5` 的 `l-4` split 不是一個穩健 basin
- 它是一個非常窄的臨界結構
- 再往 primary weak 方向推，teacher 並不會自然轉成 positive gain
- 而是更傾向回到單群配置

## 到目前為止的結論

所以現在最重要的結論不是「還差一點點就成功」，而是：

- `1|2|4|5 @ gnb_2` 雖然比前一條 family 更接近 dual-candidate regime
- 但在 `l-4` 附近，這條線也開始形成自己的 plateau

也就是說，`P3.6m` 現在真正告訴我們的是：

- 我們已經有了比較好的 family-search heuristic
- 但還需要更大一層的 scenario redesign，不能只靠單一 family 的 window-level rescaling

## 建議下一步

下一步如果進 `P3.6m-2`，比較合理的方向是：

1. 不再只改一個現成 family 的局部 window
2. 直接找新的 family source，尤其是：
   - 時間窗更長
   - 候選人競爭更穩定
   - 不會一推就 collapse
3. 或者直接升級成 family-bank / regime-bank 做批量 targeted prototypes，而不是一條一條手刻

一句話總結：

`l-6` 證明了 `l-4` 不是可穩定放大的 gain basin；`P3.6m` 下一步應該把重心放回「找更穩健的新 regime source」，而不是再磨這條已知 narrow plateau。 
