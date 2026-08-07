# P3.6q-21: focused hard-regime decision checklist

## 為什麼現在需要這份 checklist

到目前為止，`q10`、`m4b`、`o8` 已經證明一件事：

- hard regime 不是單一類型
- 同樣是 teacher 和 LE-GRA 有 gap，
  背後 bottleneck 可能完全不同

如果我們不先分類，就很容易：

- 把 selector 問題誤判成 learner 問題
- 把 final grouping 問題誤判成 candidate recovery 問題
- 在不對的地方做很多 sweep

所以這份 checklist 的目的，是讓後續 focused experiment 先做最小診斷，再決定下一步。

## 三步判斷法

### Step 1: 先問這是不是 selector-dominated failure

檢查：

- 不同 restart seed 的 support imitation 是否都差不多？
- weak margin / prototype separation 是否對不同 seed 有明顯差異？
- 換 `restart_selection_mode = margin_aware` 後，selected seed 是否改變？
- 改 seed 後，plain learner / plain grouping 是否就能直接 match teacher？

如果答案是「對」：

- 優先歸類成 selector-dominated
- 先不要急著改 supervision

代表案例：

- `q10`

### Step 2: 如果 selector 改了還不夠，再問 weak candidate path 是否已經恢復

檢查 test window：

- teacher candidate signature
- predicted top-k signature
- teacher secondary UE 是否出現在 predicted top-k
- predicted secondary rank 是否合理

如果 weak candidate path 還沒恢復：

- 不要太早測 anchor closure
- 先回頭處理 candidate recovery / supervision / representation

如果 weak candidate path 已恢復：

- 進 Step 3

### Step 3: 如果 weak top-k 已對，再問 final grouping 是否是唯一剩下的錯

檢查：

- `Multi-feature k-means` 是否已經 match teacher？
- `LE-GRA MVP` 是否仍然塌成 single-group 或少掉 secondary weak UE？
- teacher grouping 與 predicted grouping 的差異，
  是否只剩 weak closure / boundary absorption？

如果答案是「對」：

- 優先測 `candidate_anchor_hybrid`
- 這時候它是最有機會補最後一哩的最小 structural bridge

代表案例：

- `m4b`
- `o8`

## 目前三個代表 regime 的分類

### `q10`

- selector 改善有效：是
- weak top-k recovered：是
- final grouping still the main issue：有，但不是第一層

最準確分類：

- selector-dominated failure

建議第一動作：

- 先測 `margin_aware`

### `m4b`

- selector 改善有效：是
- weak top-k recovered：是
- final grouping still wrong：是

最準確分類：

- post-selector secondary weak-closure failure

建議第一動作：

- `margin_aware` 後接 `candidate_anchor_hybrid`

### `o8`

- selector 改善有效：否，selected seed 不變
- weak top-k recovered：是
- `Multi-feature k-means` 已對但 `LE-GRA MVP` 還錯：是

最準確分類：

- LE-GRA-specific grouping-path failure

建議第一動作：

- 直接測 `candidate_anchor_hybrid`

## 簡化版決策規則

如果要用一句話決定下一個 focused run：

1. 先試 `margin_aware`，看 basin 會不會變、plain path 會不會直接變好
2. 如果 weak top-k 已對，但 final grouping 還錯，就立刻試 `candidate_anchor_hybrid`
3. 只有在 weak top-k 根本沒恢復時，才優先回到 supervision / representation redesign

## 這份 checklist 的價值

它不是理論結論而已，而是直接幫我們減少無效 sweep：

- 避免把 `q10` 當成純 learner 問題
- 避免在 `m4b` 上重做 selector-only tweak
- 避免忽略 `o8` 其實只是 LE-GRA grouping path 自己出錯

所以從現在開始，新的 focused hard regime 先做這份 checklist，
再決定要不要：

- 改 selector
- 改 supervision
- 還是直接上 anchor-preserving closure
