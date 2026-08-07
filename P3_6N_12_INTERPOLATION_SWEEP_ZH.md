# P3.6n-12：interpolation sweep between `n10` and `n11`

日期：2026-08-07

## 目的

`n10` 證明我們可以把 `n5` 的 late pair 撐成 `27.9 ~ 28.8` 的 teacher-positive segment，
但 `n11` 也證明只要做一點 mild compression，這個 segment 就會整段消失。

所以 `P3.6n-12` 的目標不是再做一個大 redesign，而是把 `n10 -> n11` 中間的空間切細，
先找到：

1. teacher-positive segment 的 collapse threshold 大概落在哪
2. 在 collapse 前的最後幾個 still-positive 版本，是否已經開始變成 learner-hard

## 實作

新增：

- `build_p3_6n12_interpolation_bundle.py`

這個 builder 直接從 `n10` 出發，對 late window `27.9 ~ 28.8` 做可參數化壓縮：

- `ue4_uplift`
- `ue5_uplift`
- `strong_downshift`
- `weak_prevq`
- `strong_prevq`

## 本輪 sweep

### `n12a`: light

- bundle:
  - `p3_6n12a_interp_light/`
- parameters:
  - `ue4_uplift = 0.10`
  - `ue5_uplift = 0.05`
  - `strong_downshift = 0.00`
  - `weak_prevq = 1`
  - `strong_prevq = 4`

### `n12b`: mid

- bundle:
  - `p3_6n12b_interp_mid/`
- parameters:
  - `ue4_uplift = 0.20`
  - `ue5_uplift = 0.10`
  - `strong_downshift = 0.05`
  - `weak_prevq = 1`
  - `strong_prevq = 4`

### `n12c`: upper-mid

- bundle:
  - `p3_6n12c_interp_uppermid/`
- parameters:
  - `ue4_uplift = 0.30`
  - `ue5_uplift = 0.15`
  - `strong_downshift = 0.10`
  - `weak_prevq = 2`
  - `strong_prevq = 3`

## teacher-side 結果

### `n12a`

- late positive count:
  - `10 / 10`
- teacher-positive late segment 完整保留

### `n12b`

- late positive count:
  - `10 / 10`
- teacher-positive late segment 完整保留

### `n12c`

- late positive count:
  - `0 / 10`
- `27.9 ~ 28.8` 全部 collapse 回 single-group

## 最重要結論

目前 threshold 已經開始清楚：

- `n12b` 還完整活著
- `n12c` 已經整段死掉

也就是說，真正的 collapse boundary 現在大致就在：

- `n12b -> n12c`

之間。

## focused learner 結果：`n12b` 仍然 easy

新增：

- `p3_6n12b_kmeans_learner/`
- `p3_6n12b_hybrid_learner/`

focused protocol：

- bundle:
  - `p3_6n12b_interp_mid/bundle`
- focus UEs:
  - `3 4 5 6`
- train end:
  - `27.8`
- test:
  - `27.9 ~ 28.8`

結果：

- `Offline teacher = 0.463148622269105`
- old `kmeans_embedding` LE-GRA = `0.463148622269105`
- `hybrid_membership_kmeans` LE-GRA = `0.463148622269105`

也就是說：

- `n12b` 雖然更靠近 collapse boundary
- 但它還不是 learner-hard regime
- 因為舊 `kmeans_embedding` 一樣直接追上 teacher

## 研究判斷

這輪結果有兩個重要意義。

### 1. collapse boundary 已經被大幅收斂

我們不再只有：

- `n10` 活
- `n11` 死

這種很粗的邊界。

現在已經收斂到：

- `n12b` 活
- `n12c` 死

### 2. 在目前的 still-positive 區域裡，learner 還沒出現困難

所以現在真正缺的不是：

- 更多 bridge 修補
- 或 learner-side loss tweak

而是更精確地拆出：

- 到底是哪一個壓縮軸先把 teacher-positive segment 殺掉
- 在 teacher 還沒死之前，有沒有一小段區域會先讓舊 `kmeans_embedding` 失手

## 建議下一步

最合理的下一步是做 axis-separated threshold probe：

1. 固定 `previous_quality`
   - 只掃 CQI / strong-side downshift
2. 固定 CQI
   - 只掃 `previous_quality` compression
3. 找出哪個軸先造成 collapse
4. 在那個軸的臨界點附近再做更細一格 sweep

如果能找到：

- teacher still positive
- old `kmeans_embedding` starts failing

那才是這條 `n10` 線真正轉成新 learner-hard regime 的入口。
