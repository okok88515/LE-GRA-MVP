# P3.6q-23: 下一個最值得做、也最可能穩定放大方法差距的新 regime

## 先講結論

如果現在要押一條最可能有更大突破的路，
我會選：

- 以 `3|4|5|6 @ gnb_2` 為原始 family
- 重新做一個 **dual-boundary temporal crossover regime**

這個 regime 的目標不是單純再做一個 weak user，
而是刻意讓：

1. teacher 穩定偏好多群分法
2. `no-group` 明顯吃虧
3. `multi-feature k-means` 不容易靠單一 snapshot feature 矇對
4. `LE-GRA` 只有在用對 selector / candidate routing / anchor closure 時才會完整解出來

## 為什麼是 `3|4|5|6 @ gnb_2`

從 source family ranking 來看，正增益家族其實非常少。
目前最好的原始 family 仍然是：

- `3|4|5|6 @ gnb_2`

它有幾個很關鍵的優勢：

1. 有最長的正增益 corridor
   - best segment = `42`
   - positive snapshots = `42`
2. 本身有足夠 temporal support
   - 不像很多 family 只有 `1 ~ 4` 個 snapshot
3. 本來就有不錯的 cost / CQI / history 差異基底
4. 我們過去在這條 family 上已經驗證過：
   - 可以做出 informative split
   - 但以前很多 redesign 還不夠「穩定放大差距」

所以這條 family 最大的價值不是「它已經很難」，
而是：

- 它是目前最適合被二次設計成真正 benchmark-like hard regime 的底板

## 為什麼以前同 family 還是不夠突破

過去 `q6 ~ q9`、`n10 ~ n16` 這一串其實已經告訴我們問題在哪裡：

- 單純把某個 UE 壓弱，不夠
- 單純做 late-window smoothing，不夠
- 單純拉 CQI gap 或 resource-cost gap，也常常不夠
- 單純做 3-group ladder，teacher 不一定真的穩定選 `3-group`

也就是說，下一個 regime 不能只是：

- 再做一次 local numeric sweep

而是要同時引入三個結構條件：

1. **persistent weak anchor**
   - 固定一個真正持續偏弱的 UE
2. **dual-boundary competition**
   - 讓兩個 boundary users 都有理由被視為 secondary weak
3. **temporal crossover**
   - 讓 secondary weak 的優先次序在時間上發生切換

只有這樣，teacher / baselines / LE-GRA 才比較可能真的被分開。

## 新 regime 的核心設計

### 核心 family

- family: `3|4|5|6 @ gnb_2`

### 核心角色

- `ue4`: persistent weak anchor
- `ue5`: early-phase secondary weak candidate
- `ue6`: late-phase secondary weak candidate
- `ue3`: strong anchor

### 設計目標

讓 teacher 在同一段 regime 裡看到：

- 前段：
  - `ue4 + ue5` 應該比較像弱側
- 後段：
  - `ue4 + ue6` 應該比較像弱側

但同時要避免這件事變得太容易，
所以還要加入：

- `ue5` 與 `ue6` 在某些 snapshot 上的 `cqi_now` 很接近
- 但 `previous_quality` / `history` / `rb_scale` 指向不同方向

這樣可以自然製造：

- candidate routing ambiguity
- boundary user switching
- final grouping closure difficulty

## 這個 regime 最可能放大的差距

### 1. `teacher` vs `no-group`

如果 `ue4` 持續弱、`ue5/ue6` 有一段時間也該跟著切出去，
那 single-group 會明顯浪費資源，
所以 `teacher_gain_vs_single` 比較有機會被穩定拉高。

### 2. `teacher` vs `multi-feature k-means`

如果 `ue5` 與 `ue6` 的 snapshot CQI 很接近，
但 temporal history 與 previous-quality 指向不同切法，
plain k-means 很可能：

- 只會抓到當下最弱的 `ue4`
- 或把錯的 boundary UE 吸進弱群

這會比 `o8` / `m4b` 更容易產生穩定可觀察的結構差異。

### 3. `teacher` vs old LE-GRA grouping path

如果 weak candidate 的「第二名」會切換，
那舊 LE-GRA path 很容易：

- candidate ranking 不穩
- 或 final grouping 只保住 weak anchor，少掉 secondary UE

這就能同時測到：

- selector
- candidate routing
- anchor-preserving closure

## 我對這個 regime 的預期

理想上，它會不是單點成功，而是有一小段穩定 corridor：

- 長度目標：
  - 至少 `8 ~ 12` 個 positive snapshots

理想上 teacher 會出現：

- 穩定 `2-group`
- 並且 secondary weak 成員會從 `ue5` 漸漸切換到 `ue6`

如果成功，這會比現在的 `o8`、`m4b` 更有說服力，因為它同時具備：

- temporal support
- dual-boundary ambiguity
- structural switch

## 這條線為什麼比直接再做 q10 擴張更值得

`q10` 已經很有價值，但它現在比較像：

- selector-dominated reference case

如果再在 `q10` 上加料，
比較容易變成把同一個故事講得更厚。

相對地，這個新 regime 若成功，會補上目前故事中最欠缺的一塊：

- 一個更長、更穩定、同時能測出 routing 與 closure 的新 benchmark-like hard regime

這對論文或專題收斂更有幫助。

## 我建議的實作順序

### Step 1

先做最小 spec：

- `ue4` 固定偏弱
- `ue5 -> ue6` 做 secondary weak crossover
- 保留原始 side traffic

### Step 2

只先跑 teacher audit，不急著跑 learner

先確認：

- 是否真的有 `8 ~ 12` 個 positive snapshots
- 是否真的出現想要的 weak-side switch

### Step 3

如果 teacher corridor 成立，再進 focused learner：

- plain baseline
- `margin_aware`
- `candidate_anchor_hybrid`

## 目前最重要的一句話

如果你要的是「比現在更容易看見差距」的新 regime，
那最值得押注的不是繼續在 `q10`、`m4b`、`o8` 原地小修，
而是：

- 用 `3|4|5|6 @ gnb_2` 做一個有 persistent weak anchor、
  dual-boundary competition、temporal crossover 的新 targeted regime。
