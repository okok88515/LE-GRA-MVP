# P3.6n-6 Masked Pair Failure

日期：2026-08-07

## 目的

`P3.6n-5` 雖然成功造出 late weak pair `{ue4, ue5}`，
但 learner / baseline 仍然太容易跟上。

所以 `P3.6n-6` 的想法是：

- 保留 late weak-pair 結構
- 但把弱群在簡單 CQI / history 特徵上的可分性壓低
- 測試 teacher 是否仍會維持分群

## 實作

腳本：

- `build_p3_6n6_masked_pair_bundle.py`

bundle：

- `p3_6n6_masked_pair_bundle/`

核心改動：

- 以 `p3_6n5_temporal_swap_bundle/` 為基底
- 在 `27.9s ~ 29.9s`：
  - 把 target family 的 `rb_available` 再壓到 `3`
  - 讓 `ue4`、`ue5` 的 rate 更差
  - 但同時把 `ue3`、`ue4`、`ue5`、`ue6` 的 `previous_quality` 都壓回 `3`
  - 並把 `ue4` / `ue5` 的 CQI 拉回中間區間，降低簡單特徵上的對比

## 結果

輸出：

- `p3_6n6_teacher_audit/`
- `p3_6n6_focus_mining/`

整體 summary：

- `positive_gain_count = 30`
- `max_teacher_gain_vs_single = 0.07945174187052606`

但這個正增益其實主要仍來自早段 `ue5-only` regime。

真正關鍵的 late window `27.9s ~ 29.9s` 上：

- teacher 全部回到 single-group
- `positive scenario count = 0 / 21`

也就是說：

- masked late pair 沒有撐住 teacher 的分群動機

## 解讀

這個失敗很重要，因為它回答了我們一個核心問題：

> 會不會只要有 rate / pressure 差異，teacher 就會自然想分群？

目前答案是：

- 不會

在這條 family 上，若把晚段的 CQI / history gap 壓得太平，
即使還保留 rate 壓力，teacher 也會直接退回 single-group。

換句話說：

- 這條 regime 的 teacher-positive 結構
- 目前仍然依賴「看得見的品質落差」
- 而不是純粹靠隱性的 rate / pressure mismatch 就能成立

## 結論

`P3.6n-6` 雖然失敗，但它提供了明確邊界：

- fully masked weak pair:
  - 太弱，teacher 不分
- plainly visible weak pair:
  - teacher 會分，但 baseline 也容易分

所以下一步不該再往「完全遮蔽」走，
而是要做折衷版：

- 保留一定程度可見品質差
- 但把 late weak pair 拉長、拉穩
- 再逐步壓低簡單特徵上的可分性

也就是從：

- full masking

改成：

- partial masking with sustained teacher-positive pair regime
