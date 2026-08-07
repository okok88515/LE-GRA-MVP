# P3.6n-11：mild compression collapse on top of `n10`

日期：2026-08-07

## 目的

`n10` 已經成功把 `n5` 的 late pair segment 從 `27.9 ~ 28.3` 拉長到 `27.9 ~ 28.8`，
但 focused learner validation 也證明它目前仍然是 easy / already-solvable。

所以 `n11` 的目標很直接：

- 保留 `n10` 已經成功的 rate / pressure structure
- 只對 late window 做很輕微的 simple-feature separability compression
- 看 teacher-positive pair segment 能不能還活著

## 設計

新增：

- `build_p3_6n11_state_hold_mild_compression_bundle.py`
- `p3_6n11_state_hold_mild_compression_bundle/`
- `p3_6n11_teacher_audit/`
- `p3_6n11_focus_mining/`

修改範圍：

- 只動 `27.9s ~ 28.8s`
- 保留 `n10` 的 late-state hold
- 但把簡單特徵做最小壓縮：
  - `ue4` CQI 稍微提高、`previous_quality` 從 `1 -> 2`
  - `ue5` CQI 稍微提高
  - `ue3` / `ue6` CQI 稍微降低、`previous_quality` 從 `4 -> 3`

也就是說：

- 這不是像 `n6` 那樣的 full masking
- 只是很溫和地把 weak 與 strong 的 user-side可分性壓近一點

## 結果

teacher audit 顯示：

- late window `27.9s ~ 28.8s`
  - positive scenario count = `0 / 10`
- 全部都回到：
  - `[[0,1,2,3]]`
  - single-group

focus mining 結果：

- `positive_segment_count = 1`
- 但唯一剩下的 segment 只回到早期：
  - `25.8s ~ 27.8s`
- `n10` 才剛救回來的 late pair segment 已完全消失

## 解讀

這個結果非常重要，因為它畫出了一條新的 failure boundary：

- `n10` 證明：
  - 這條 family 可以被整理成較長的 late pair segment
- `n11` 證明：
  - 即使只做 mild compression，
    teacher-positive late segment 也會立刻 collapse

換句話說，現在不是「我們還沒找到正確的 learner tweak」，
而是：

- `n10` 這條 source 雖然已經有 segment
- 但它對 simple-feature compression 的容忍度非常低

## 目前最重要結論

`n10 -> n11` 這組結果把這條線的研究狀態說得很清楚：

1. `n10` 是可延長的 positive source
2. 但還太容易
3. 一旦做輕度 compression，segment 就會直接消失

所以這條線的下一步不是立刻進 learner-side，而是要先找到更細緻的中間地帶：

- 不像 `n10` 那麼容易
- 也不像 `n11` 那樣直接死掉

## 建議下一步

最合理的下一步是做更細粒度的 interpolation sweep：

1. 以 `n10` 為 base
2. 只調一個軸，少量掃：
   - `ue4` CQI uplift
   - strong-side CQI downshift
   - `previous_quality` compression
3. 找出哪個最先把 teacher-positive late segment 壓死
4. 把真正的 collapse threshold 找出來

如果能在這條 threshold 附近找到：

- teacher 仍 split
- 但舊 `kmeans_embedding` 開始 miss

那才會是這條 family 變成新 learner-hard regime 的入口。
