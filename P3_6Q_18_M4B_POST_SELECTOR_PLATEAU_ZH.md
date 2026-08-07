# P3.6q-18: `m4b` 在 selector 改善後仍卡住的真正原因，是 secondary weak UE 的最終切分沒有被帶出來

## 背景

在 `P3.6q-17` 我們已確認：

- `margin_aware` restart selector 會把 `m4b` 的 selected seed 從舊路徑切到 seed `11`
- 但 utility 只到 `0.5790831051936908`
- `Offline teacher = 0.5796090488051922`

也就是說：

- basin 確實換了
- 但換 basin 本身還不夠讓 `m4b` 完整過關

所以這一輪要回答的問題不是「selector 有沒有幫助」，而是：

- selector 幫完之後，`m4b` 還剩下哪一層 bottleneck？

## 核心檢查

檢查 artifact：

- `p3_6q16_m4b_margin_selector/restart_candidates.csv`
- `p3_6q16_m4b_margin_selector/weak_group_prediction_audit.csv`
- `p3_6q16_m4b_margin_selector/teacher_group_evidence_audit.csv`
- `p3_6q16_m4b_margin_selector/teacher_imitation_diagnostics.csv`

## 發現 1：support-train imitation 已經無法區分 seed，margin 只是幫忙挑比較穩的 basin

三個 restart seed 在 support imitation 上其實都一樣：

- support pairwise accuracy = `1.0`
- support ARI = `1.0`
- support NMI = `1.0`

真正有差的是 weak margin：

- seed `7`: `support_weak_margin_min = 0.0862`
- seed `9`: `support_weak_margin_min = -0.0409`
- seed `11`: `support_weak_margin_min = 0.1106`

所以 `m4b` 的 selector 改善不是因為發現了新的 support imitation pattern，而是：

- 當 support imitation 全滿分時
- margin-aware selector 至少能避開 weak margin 不穩的 basin

這解釋了為什麼它會換到 seed `11`。

## 發現 2：focus test 上其實已經知道 teacher 的 weak candidate 是 `15|4`

在 `43.7s ~ 43.9s`：

- teacher candidate signature = `15|4`
- predicted top-k signature = `15|4`
- teacher secondary UE = `4`
- predicted secondary rank = `2`

也就是說 learner 並沒有把 `ue4` 完全看丟。

更精確地說：

- top-1 weak UE 是 `15`
- top-2 weak UE 是 `4`
- 所以 candidate path 本身已經對齊 teacher

這點非常重要，因為它把 bottleneck 從「candidate recovery」往後推了一層。

## 發現 3：真正失敗發生在 final grouping，不是在 candidate ranking

Teacher imitation diagnostics 顯示：

- teacher grouping: `0|1|2|3|5 / 15|4`
- predicted grouping: `0|1|2|3|4|5 / 15`

也就是：

- learner 已經知道弱側應該是 `15` 加 `4`
- 但 final grouping 只把 `15` 單獨切出去
- `ue4` 在最後一步又被吸回強群

因此 `m4b` 現在最準確的 diagnosis 是：

- not a selector failure
- not a weak-candidate discovery failure
- it is a **secondary weak UE extraction failure at the final grouping step**

## 發現 4：這個 plateau 很小，但它正好暴露出目前方法的結構上限

這次 gap 很小：

- utility gap vs teacher = `-0.0005259436115013782`

但這個小 gap 代表的不是「沒差」，
而是更麻煩的事情：

- 現有 learner / grouping pipeline 已經能抓到主 weak UE
- 也能把 secondary weak UE 放進 top-k
- 但沒有足夠強的結構把 secondary weak UE 穩定拉進 final weak cluster

換句話說，目前方法對「弱側主核心」有效，
但對「弱側邊界成員」仍然不夠穩。

## 對研究方向的意義

這讓 `q10` 與 `m4b` 的差別更清楚：

- `q10`: selector-dominated failure
- `m4b`: post-selector structural failure

而 `m4b` 的結構瓶頸又可以再細分成：

- weak candidate path 已恢復
- 但 weak group closure / boundary absorption 還沒恢復

所以接下來如果還要打 `m4b`，
重點不應該再放在：

- replay-only
- selector-only
- top-k candidate calibration-only

而應該放在更直接的「secondary weak UE 被吸回強群」問題上。

## 建議下一步

最值得做的不是再 sweep selector，而是做最小的 post-selector 結構測試：

1. 在 inference/grouping 端加入更明確的 secondary-anchor closure
   - 已知 top-1 = `15`、top-2 = `4`
   - 測試是否能在 final grouping 時優先保留 `15|4` 成對切分
2. 或者在 train-side 加強 secondary weak UE 的 boundary retention
   - 不是再提高 top-k hit
   - 而是提高 secondary weak UE 不被吸回主群的機率

最重要的是：

- `m4b` 現在不需要更多 selector 微調
- 它需要的是針對 secondary weak UE 的 localized structural fix
