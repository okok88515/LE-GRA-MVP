# P3.6m-16 Focused Multi-start Tie-break

日期：2026-08-06

## 這一步在解什麼

前一輪 `P3.6m-15` 已經把現象釐清了：

- 兩張 exact dual-weak support snapshot + 短 warmup 的 recipe 是真的有效
- 但結果有明顯 seed sensitivity
  - seed `7`：三個 transfer case 全成功
  - seed `11`：三個 transfer case 全成功
  - seed `9`：三個 transfer case 全失敗

所以現在的問題已經不是「learner 能不能學會」，而是：

- 怎麼穩定挑到會成功的那條 training trajectory

## 採取的最小改動

不改 learner 主架構，只在 focused temporal learner 外面加一層
deterministic multi-start selection。

修改檔案：

- `run_p3_6g_temporal_learner.py`

新增能力：

- `--restart-seeds`

流程：

1. 對每個 restart seed 各 train 一個 candidate
2. 在 exact support slices 上計算 candidate 的 support-side 指標
3. 輸出 `restart_candidates.csv`
4. 依固定規則選出最終模型

## Candidate selection 規則

排序優先順序：

1. support pairwise accuracy 越高越好
2. support ARI 越高越好
3. support NMI 越高越好
4. support utility 越高越好
5. support 與 teacher 的 utility gap 絕對值越小越好
6. 若以上完全平手，選 training selection loss 較低者

這個最後一項很重要，因為目前 support-side imitation signal 還不夠強，
常常分不出 seed `7` 與 `11`。

## 實驗設定

共同設定：

- family/regime：`0|1|15|2|3|4|5 @ gnb_1`
- bundle：`p3_6m4b_threshold_nudge_bundle/bundle`
- `background_train_limit = 150`
- `focus_train_repeat = 2`
- `focus_only_warmup_epochs = 1`
- `restart_seeds = [7, 9, 11]`
- 主呼叫 seed 仍設成 `9`，讓我們直接測試能否救回原本 fail 的 case

三個 transfer case：

1. `43.7 + 43.8 -> 43.9`
2. `43.8 + 43.9 -> 43.7`
3. `43.7 + 43.9 -> 43.8`

對應輸出：

- `p3_6m16_multistart_support437_438_test439/`
- `p3_6m16_multistart_support438_439_test437/`
- `p3_6m16_multistart_support437_439_test438/`
- `p3_6m16b_multistart_tiebreak_support437_438_test439/`
- `p3_6m16b_multistart_tiebreak_support438_439_test437/`
- `p3_6m16b_multistart_tiebreak_support437_439_test438/`

## 結果

### 1) Multi-start 本身有效

三個 case 在 multi-start 版本都恢復到 teacher-level utility：

- `LE-GRA utility = teacher utility = 0.579609048805`

### 2) 單看 support imitation 還不夠

在 `p3_6m16b_*` 三個 case 中，三個 candidate seed 的 support metrics 完全一樣：

- pairwise = `0.714285714286`
- ARI = `0.416666666667`
- NMI = `0.428140178120`
- support utility gap = `-0.000525943612`

也就是說：

- support slice 上的顯式 imitation 指標，還不足以分辨哪個 restart
  會在鄰近 holdout slice 上真的成功

### 3) 目前最有用的 tie-break 是 training loss

三個 case 最後都選到 seed `11`，因為它的 training selection loss 最低：

- `43.7 + 43.8 -> 43.9`
  - seed 7 loss = `0.004010846719`
  - seed 9 loss = `0.004361897524`
  - seed 11 loss = `0.003429105416`
- `43.8 + 43.9 -> 43.7`
  - seed 7 loss = `0.004190595017`
  - seed 9 loss = `0.004627169265`
  - seed 11 loss = `0.003681235678`
- `43.7 + 43.9 -> 43.8`
  - seed 7 loss = `0.004177344767`
  - seed 9 loss = `0.004620457626`
  - seed 11 loss = `0.003722326015`

## 目前最重要的研究結論

這一步最重要的不是「multi-start 比單 seed 好」而已，而是：

1. 目前 learner 已經具備學會這個 local dual-weak rule 的能力
2. 現在真正的短板是 selection / validation signal，而不是表達能力本身
3. exact support imitation 指標不足以當唯一 selector
4. 低 training loss 目前可以當一個有效、可重現的 deterministic tie-break

## 我認為這一步的定位

這是一個很合理的暫時停損點。

因為到這裡我們已經拿到三層結論：

- 第一層：不是 learner 永遠學不會，而是 evidence density / curriculum 有門檻
- 第二層：兩張 support snapshot 的最小成功集可以在三個方向 transfer
- 第三層：即使有 seed sensitivity，也可以用 focused multi-start + deterministic
  tie-break 把成功解穩定挑出來

## 下一步建議

我不建議下一步直接擴大整體矩陣。

比較值得做的是二選一：

1. 把 focused multi-start 視為目前正式 protocol
   - 先用它當作後續 focused learner 評估標準

2. 繼續做更乾淨的 selector
   - 想辦法找到比 support imitation 更能預測 holdout transfer 成敗的 local
     validation signal

如果要繼續沿 learner-focused 方向前進，我會優先做第 2 點。
