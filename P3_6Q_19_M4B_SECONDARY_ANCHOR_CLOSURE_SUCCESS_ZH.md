# P3.6q-19: `candidate_anchor_hybrid + margin_aware` 在 `m4b` 成功把 secondary weak UE 拉進最終 weak group

## 背景

`P3.6q-18` 已經把 `m4b` 的 bottleneck 描述得很清楚：

- selector 已經改善
- weak candidate path 也已經對齊 teacher
- 但 final grouping 還是把 `ue4` 吸回強群

所以這一輪的問題非常聚焦：

- 如果我們在 final grouping 直接保留 top weak-score anchor，
  能不能把已經恢復的 `15|4` candidate path 真的變成最終 split？

## Probe 設定

Run:

- `p3_6q19_m4b_candidate_anchor_margin_selector/`

Command:

```powershell
python run_p3_6g_temporal_learner.py `
  --bundle-dir p3_6m4b_threshold_nudge_bundle\bundle `
  --out-dir p3_6q19_m4b_candidate_anchor_margin_selector `
  --focus-ue-ids 0 1 15 2 3 4 5 `
  --background-train-limit 150 `
  --train-window-end 43.6 `
  --test-window-start 43.7 `
  --test-window-end 43.9 `
  --max-groups 3 `
  --epochs 12 `
  --restart-seeds 7 9 11 `
  --grouping-mode candidate_anchor_hybrid `
  --restart-selection-mode margin_aware
```

這裡沒有改 learner loss，也沒有再做新的 supervision tweak。
只做兩件事：

1. selector 用 `margin_aware`
2. final grouping 用 `candidate_anchor_hybrid`

## 結果

主結果：

- selected restart seed = `11`
- `Offline teacher = 0.5796090488051922`
- `LE-GRA MVP = 0.5796090488051922`

也就是：

- `m4b` 在這個 focused regime 上正式達成 teacher match

## 關鍵 diagnostics

### 1. weak candidate path 本來就已經是對的

在 `43.7s ~ 43.9s`：

- teacher candidate signature = `15|4`
- predicted top-k signature = `15|4`
- predicted top-1 weak UE = `15`
- predicted top-2 weak UE = `4`

這再次確認：

- 之前的卡點真的不是 candidate discovery

### 2. 真正被修好的，是 final grouping 的 weak closure

之前 `margin_aware + kmeans_embedding` 的 grouping 是：

- predicted = `0|1|2|3|4|5 / 15`

現在 `candidate_anchor_hybrid + margin_aware` 變成：

- predicted = `15|4 / 0|1|2|3|5`

和 teacher 等價：

- teacher = `0|1|2|3|5 / 15|4`

所以這次成功不是「分數剛好補上」，
而是結構上真的把 `ue4` 跟 `ue15` 一起保住了。

## 結論

`m4b` 這次的突破非常有研究價值，因為它把 `P3.6q-18` 的 diagnosis 直接驗證了：

- 如果 top-k candidate 已經恢復
- 那最小的 secondary-anchor closure 就足以補掉最後的 teacher gap

也就是說：

- `m4b` 並不需要更強的 selector tweak
- 也不一定需要更重的 learner-side supervision redesign
- 在這個 regime 上，
  一個最小的 inference/grouping structural bridge 就已經足夠

## 對整體研究的意義

現在 `q10` 與 `m4b` 的故事可以連成更完整的兩段式脈絡：

1. `q10` 告訴我們：
   - 有些失敗其實是 selector 沒挑到對 basin
2. `m4b` 告訴我們：
   - 即使 basin 已對、candidate path 已對，
     final grouping 還是可能少掉 secondary weak UE
   - 這時候最小的 anchor-preserving closure 可以補上最後一哩

所以目前最準確的高層結論是：

- bottleneck 不是單一的
- hard regimes 至少分成：
  - selector-dominated
  - post-selector weak-closure dominated

## 建議下一步

接下來最值得做的不是立刻擴大 matrix，
而是先做小型 transfer check：

1. 這個 `candidate_anchor_hybrid + margin_aware` 組合
   是否也能幫助其他 post-selector structural regime？
2. 尤其是：
   - `o8` 如果 candidate path 本來沒恢復，理論上這招應該不會幫太多
   - 這可以拿來驗證「candidate recovered 才值得做 anchor closure」這條判準

也就是說，下一步應該是：

- 把這個方法當成一個有條件成立的 structural bridge
- 去驗證它適用於哪些 regime，而不是直接把它當萬用解
