# P3.6m-18 Sibling Bundle Protocol Check

日期：2026-08-06

## 這一步在驗證什麼

`P3.6m-17` 已經證明：

- 在 `p3_6m4b_threshold_nudge_bundle`
- 只要用正確的 normalized support scoring
- restart selector 就能把壞 seed 排掉，選出能成功 transfer 的 candidate

但那還有一個關鍵問題：

- 這是不是只對 `m4b` 這個很窄的 dual-weak regime 有效？

所以 `P3.6m-18` 要做的是：

- 不換太遠的 family
- 直接回到最接近的 sibling bundle
- 看這個 protocol 能不能也把它救起來

## 為什麼選 `p3_6m2_positive_family_decoy_bundle`

因為它剛好是最有資訊量的相鄰案例：

- family 一樣：`0|1|15|2|3|4|5 @ gnb_1`
- 但是 bundle 不是 `m4b`
- 它就是當初 `P3.6m-3` 裡那個：
  - `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`

也就是說：

- 這不是一個「本來就太簡單」的 sibling
- 也不是完全不同 family
- 而是很適合測 protocol 外部有效性的近鄰

## 實驗設定

指令：

```powershell
python run_p3_6g_temporal_learner.py `
  --bundle-dir p3_6m2_positive_family_decoy_bundle/bundle `
  --out-dir p3_6m18_m2_normalized_selector_multistart `
  --focus-ue-ids 0 1 15 2 3 4 5 `
  --background-train-limit 150 `
  --train-window-end 43.7 `
  --test-window-start 43.8 `
  --test-window-end 43.9 `
  --max-groups 3 `
  --epochs 12 `
  --seed 9 `
  --restart-seeds 7 9 11 `
  --min-users 2
```

輸出：

- `p3_6m18_m2_normalized_selector_multistart/`

## 主結果

結果很清楚：

- 這個 protocol 沒有把 `m2` 救起來

最後 summary：

- `selected_restart_seed = 9`
- `teacher utility = 0.579609048805`
- `LE-GRA utility = 0.579083105194`

也就是：

- 最終結果和原始 `P3.6m-3` 幾乎一樣
- 這不是 selector 換一下就能解的 case

## Candidate-level restart 結果

`restart_candidates.csv` 顯示：

- seed `7`
  - `support_pairwise_accuracy = 0.999457847655`
  - `support_utility_gap = -9.979954677e-07`
  - `selection_validation_loss = 0.002159013169`
- seed `9`
  - `support_pairwise_accuracy = 0.999457847655`
  - `support_utility_gap = -9.979954677e-07`
  - `selection_validation_loss = 0.000939194734`
- seed `11`
  - `support_pairwise_accuracy = 0.999457847655`
  - `support_utility_gap = -9.979954677e-07`
  - `selection_validation_loss = 0.002167450808`

這代表什麼？

- 三個 seed 在 support train 上幾乎沒有可分辨差異
- 不是像 `m4b` 那樣會自然分成：
  - 好 seed
  - 壞 seed

## 我額外做的 boundary / positive-gain 子集分析

為了確認不是「全 support 平均把訊號沖淡」，我又額外檢查了：

1. 全部 support
2. 只有 positive-gain support
3. 靠近 test 的 boundary support

`m2` train set 結構：

- all support = `527`
- positive-gain support = `7`
- boundary support = `4`

結果三個 seed 仍然完全一樣：

- all-support pairwise = `0.999457847655`
- positive-gain-support pairwise = `0.959183673469`
- boundary-support pairwise = `0.928571428571`
- holdout pairwise = `0.714285714286`

而且：

- seed `7` / `9` / `11`
- 全部都收斂到同一種 holdout 錯誤

## 這一步最重要的結論

這一步很重要，因為它把兩種 failure 分開了：

### `m4b` 類型 failure

- learner 其實有成功解
- 只是 selector 原本在錯的 feature space 上評分
- 修正後可以把壞 seed 排掉

### `m2` 類型 failure

- 不是 selector 選錯
- 而是目前 learner recipe 本身就會把不同 seed 收斂到同一個錯誤局部解

所以 `P3.6m-18` 告訴我們：

- restart / tie-break engineering 已經不是接下來最值得花時間的地方

## 對下一步的影響

下一步不該再做：

- 更多 restart seeds
- 更花的 tie-break 規則
- 單純 selector 微調

更值得做的是改變 broader mixed-support regime 的有效訓練訊號，例如：

1. boundary-aware support weighting
2. 只強調 positive-gain / near-test 視窗的 curriculum
3. regime-local subset selection

## 我對目前狀態的判斷

到這裡，研究脈絡已經很清楚：

- `P3.6m-17` 解的是 selector-space mismatch
- `P3.6m-18` 證明 broader sibling-bundle failure 不是 selector 問題

所以如果接下來還要往前推，
最合理的方向就是：

- 不再問「怎麼選 seed」
- 改問「怎麼讓 mixed-support train set 裡真正關鍵的 boundary evidence 被 learner 更重視」
