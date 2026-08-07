# P3.6q-17: margin-aware selector helps q10 and m4b, stays neutral on n3, but does not fix o8

## 目的

`P3.6q-16` 證明：

- 在 `q10` 上，單靠 `margin_aware` restart selection 就能把 plain learner 從失敗拉回 teacher match

但這還不夠。

真正要回答的是：

- 這是不是只對 `q10` 有效？
- 還是它在其他 regime 也能更穩定地找到好 basin？

所以這一步做一個最小 transfer check，挑三種代表性 regime：

1. easy regime: `n3`
2. bridge-needed but short regime: `o8`
3. hard dual-weak regime: `m4b`

## 結果總表

| Regime | Original selector | Margin-aware selector | Outcome |
|---|---|---|---|
| `n3` | seed `7` | seed `7` | no change, still teacher match |
| `o8` | seed `7` | seed `7` | no change, still fail |
| `m4b` | old baseline seed `9` | seed `11` | basin changed, utility still slightly below teacher |
| `q10` | seed `9` | seed `11` | basin changed, now teacher match |

## n3

Artifact:

- `p3_6q16_n3_margin_selector/`

結果：

- selected restart seed = `7`
- `LE-GRA MVP = 0.4603881335630136`
- `Offline teacher = 0.4603881335630136`

解讀：

- 在已經 easy / solvable 的 regime 上，margin-aware selector 沒有造成 regression
- 這是好的，代表它至少不會亂破壞已經穩定的 case

## o8

Artifact:

- `p3_6q16_o8_margin_selector/`

結果：

- selected restart seed = `7`
- `LE-GRA MVP = 0.6071841780840183`
- `Offline teacher = 0.6198214236671593`

解讀：

- selector 沒有改變 basin
- 也沒有修掉 `o8`

這很重要，因為它表示：

- `o8` 的問題不是簡單的 basin mis-selection
- 它仍然更像 inference-path / grouping-path bottleneck

## m4b

Artifact:

- `p3_6q16_m4b_margin_selector/`

結果：

- selected restart seed = `11`
- `LE-GRA MVP = 0.5790831051936908`
- `Offline teacher = 0.5796090488051922`

解讀：

- margin-aware selector 確實改變了 basin
- 但它沒有把 `m4b` 完全修成 teacher match

所以 `m4b` 的訊號是：

- basin selection 有幫助
- 但它不是全部答案

## 綜合解讀

現在 selector 線的最準確結論是：

### 1. margin-aware selector 不是萬靈丹

它不能：

- 普遍修掉所有 hard regime

因為：

- `o8` 完全沒動
- `m4b` 只出現 basin 改變，但沒有 full recovery

### 2. 但它也不是 q10 特例

因為在 `m4b` 上它也確實改變了 selected basin：

- `9 -> 11`

這說明：

- selector 確實是一條真實 research lever
- 不只是 `q10` 偶然有效

### 3. 不同 regime 的主 bottleneck 仍然不同

- `q10`: selector 是一級瓶頸，修完就能直接成功
- `m4b`: selector 有幫助，但後面仍有 harder learner/grouping bottleneck
- `o8`: selector 幾乎不是核心問題，主瓶頸仍在 grouping / bridge path

## 下一步建議

基於這輪 transfer check，最合理的下一步不是直接把 `margin_aware` 設成全域預設，而是：

1. 保留它作為 experimental selector
2. 在之後的 focused hard-regime 驗證中，同時報：
   - `support_imitation`
   - `margin_aware`
3. 把 regime 分成兩類來思考：
   - selector-dominated failures
   - post-selector structural failures

如果只選一條主線先做，我會建議：

- 在 `q10` 和 `m4b` 上做更細的 per-seed / per-regime selector audit

因為現在我們已經知道：

- selector can unlock hidden good basins,
- but whether that is enough depends on the regime.
