# P3.6m-19：最小版 boundary-aware support weighting

日期：2026-08-06

## 這一步在做什麼

`P3.6m-18` 已經證明一件很重要的事：

- 在 `p3_6m2_positive_family_decoy_bundle` 這個 sibling bundle 上，
  問題**不只是** restart selector 選錯 seed
- 因為 seed `7 / 9 / 11` 在 normalized support scoring 下幾乎看起來一樣，
  但 holdout 還是一起卡在錯的 local rule

所以這一步不再繼續修 selector，而是改成做一個最小、低風險、可回退的
learner-side 改動：

- 不改 `train_trace_model(...)` 主架構
- 不新增新的 head
- 不重寫 supervision loss
- 只在資料餵入順序與權重上，加入「boundary-aware support replay」

核心想法是：

- 如果 learner 真正缺的是「接近 regime boundary 的弱訊號」
- 那我們先不要大改模型
- 先試最小版的作法：把少量、晚期、而且確實是 positive-gain 的 support
  slice 多餵幾次，看 learner 會不會因此改變 decision boundary

## 實作內容

修改檔案：

- `run_p3_6g_temporal_learner.py`

新增邏輯：

- `_select_boundary_support_indices(...)`
  - 從 `focus_train` 裡挑出：
    - timestamp `>= boundary_support_start`
    - 若有指定，則必須是 positive-gain slice
- `_repeat_selected_examples(...)`
  - 將被選中的支援 slice 額外重播多次

新增 CLI 參數：

- `--boundary-support-start`
- `--boundary-support-repeat`
- `--boundary-support-positive-only`

設計原則很保守：

- 原本的 `background_train` 不動
- 原本的 `focus_train` 不動
- 只是把少數 boundary support 例子額外 replay
- replay 次數 = `boundary_support_repeat - 1`

另外把以下資訊寫進 `split_summary.json`：

- `boundary_support_start`
- `boundary_support_repeat`
- `boundary_support_positive_only`
- `boundary_support_selected_scenarios`
- `effective_boundary_support_scenarios`

## 實驗設定

主測試對象：

- bundle: `p3_6m2_positive_family_decoy_bundle/bundle`
- family: `0|1|15|2|3|4|5 @ gnb_1`

固定設定：

- `train_window_end = 43.7`
- `test_window_start = 43.8`
- `test_window_end = 43.9`
- `restart_seeds = 7 9 11`
- `boundary_support_start = 43.4`
- `boundary_support_positive_only = true`

這個條件下，被選中的 boundary-positive support slice 只有：

- `1` 個

也就是說，這一步其實是在測：

- 「只多播一個非常局部、但靠近邊界的 support slice」
- 能不能把 learner 從原本的 plateau 拉開

## repeat sweep

輸出資料夾：

- `p3_6m19b_m2_boundary_weighting_r1/`
- `p3_6m19b_m2_boundary_weighting_r4/`
- `p3_6m19b_m2_boundary_weighting_r8/`
- `p3_6m19b_m2_boundary_weighting_r16/`

### r1：基準版

- selected restart seed = `9`
- selected boundary support = `1`
- effective extra replay = `0`
- `LE-GRA utility = 0.579083105194`
- `teacher utility = 0.579609048805`
- gap = `-0.000525943612`

這其實就是原本 `P3.6m-18` 的狀態，還卡在：

- `teacher > LE-GRA = CQI = resource-cost = multi-feature`

### r4：開始影響 selector，但還沒影響 holdout

- selected restart seed = `11`
- effective extra replay = `3`
- `LE-GRA utility = 0.579083105194`
- 對 teacher gap 沒縮小

這一步很值得注意，因為它表示：

- replay 已經開始影響 support-side 選擇
- 但還不夠強，還沒真的把最終 holdout grouping 推過去

換句話說：

- 不是完全沒效
- 而是 signal strength 還沒過門檻

### r8：開始真的動

- selected restart seed = `11`
- effective extra replay = `7`
- `support_selection_pairwise_accuracy = 1.0`
- `LE-GRA utility = 0.579346076999`
- gap to teacher = `-0.000262971806`

這代表：

- boundary replay 不只改 selector
- 也開始改變 learner 在 holdout 上的實際落點

雖然還沒完全追上 teacher，但已經不是原本那條平盤。

### r16：直接追平 teacher

- selected restart seed = `7`
- effective extra replay = `15`
- `support_selection_pairwise_accuracy = 1.0`
- `LE-GRA utility = 0.579609048805`
- 與 teacher utility 完全一致

這是目前最重要的新證據。

## 目前最重要的研究解讀

這一步的意義非常明確：

1. `m2` 並不是完全無法靠 learner-side 小改動救回來  
   先前我們知道 selector 修好之後，`m2` 還是卡住，所以曾懷疑需要更大規模
   的 learner redesign。  
   但現在看到，只靠最小版 boundary-aware replay，就已經能把結果往 teacher 推。

2. 真正缺的，很可能是「邊界附近的有效 supervision 密度」  
   不是所有 support 都一樣有用。  
   當我們把靠近 `43.4s+`、而且已知是 positive-gain 的 support slice 加權，
   learner 才開始脫離原本 plateau。

3. 這看起來像是有 threshold 的現象，不是線性小改善  
   `r4` 幾乎還沒動，`r8` 開始動，`r16` 直接追平 teacher。  
   這種形狀比較像是：
   - boundary signal 低於某個強度時，模型還是回到舊解
   - 一旦超過門檻，就能切到比較對的 local rule

4. 這比盲目擴大矩陣更值得先追  
   因為我們現在不是在刷更多平均數，而是第一次抓到「可操作的機制」：
   - boundary slice 的密度
   - replay 強度
   - support subset 定義

## 這一步的限制

雖然結果很好，但還不能過度解讀。

目前限制有三個：

1. 只驗證在 `m2` 這一個 sibling bundle
2. 只重播到 `1` 個 boundary-positive support slice
3. holdout 還是很短，只看 `43.8s ~ 43.9s`

所以目前比較準確的說法不是：

- 「問題解完了」

而是：

- 「我們已經找到一個能真正推動 learner 的局部 supervision 機制」

## 建議的下一步

最合理的下一步不是立刻擴整體矩陣，而是先做小而準的 robustness check：

1. 小範圍驗證 replay 強度是否穩定  
   例如在同 family 內做極小幅時間窗移動，看 `r16` 是否仍有效。

2. 測試 boundary subset 定義  
   例如：
   - `43.3` / `43.4` / `43.5`
   - positive-only vs. boundary-all

3. 檢查是否真的學到 secondary weak candidate，而不只是偶然配平 utility  
   也就是要回頭看 grouping 組成、pairwise、弱組內容。

## 目前一句話結論

最小版 `boundary-aware support weighting` 已經在 `m2` 上提供了第一個清楚證據：

- `LE-GRA` 不是學不動
- 而是之前缺少足夠強、足夠靠近 regime boundary 的有效 support supervision
