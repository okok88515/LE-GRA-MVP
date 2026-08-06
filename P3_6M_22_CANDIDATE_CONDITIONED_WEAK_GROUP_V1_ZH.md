# P3.6m-22：最小版 candidate-conditioned weak-group supervision v1

日期：2026-08-06

## 這一步在做什麼

在 `P3.6m-21` 我們已經確認：

- `boundary-aware replay` 在 `m2` 上有效
- 但 transfer 到 `m4b` 失敗

而且失敗得很關鍵：

- support-side imitation 已經 perfect
- replay 也已經確實加進去了
- 可是 holdout 還是 stuck 在舊解

這表示現在的問題已經不能再簡化成：

- 「boundary 支援樣本不夠重」

更可能是：

- learner 還沒有被足夠明確地教會 secondary weak candidate

所以這一步我做的是一個最小版的 learner-side refinement：

- 不改模型架構
- 不重寫 grouping head
- 不改 inference path
- 只在現有 weak-group membership supervision 上，
  再額外加一個 sparse candidate-conditioned BCE

## 設計原則

我們現在最在意的是：

- 在 teacher hardest group 裡
- learner 容易只抓到最明顯的 primary weak user
- 卻忽略 secondary weak candidate（例如 `ue4`）

所以這版設計非常直接：

1. 先找 teacher 的 hardest group
2. 在 hardest group 裡，用 mean resource-cost 排序
3. 取前 `k` 個當 weak-group candidates
4. 對這些 candidate 額外加 weak-membership BCE
5. 並且把第二名 candidate 再額外放大權重

這樣做的好處是：

- 它直接把 supervision 壓到我們真的關心的人身上
- 但又不需要大改整個 learner 主體

## 程式實作

### 1. `le_gra_mvp.py`

新增：

- `candidate_conditioned_membership_targets(...)`

功能：

- 輸入 teacher groups 與 scenario
- 找出 hardest group
- 按 mean resource-cost 對 hardest group 成員排序
- 回傳：
  - `candidate_target`
  - `candidate_target_weights`

目前 v1 的規則：

- 第一名 candidate 權重 = `1.0`
- 第二名 candidate 權重 = `secondary_scale`

另外在：

- `MLPEncoder.train_step(...)`

新增參數：

- `candidate_target`
- `candidate_target_weights`
- `candidate_membership_weight`

這個新 loss 是：

- sparse candidate-membership BCE

它只作用在 candidate mask 有開啟的位置。

### 2. `run_p3_6_coupled_learner.py`

把這組 supervision 接進：

- `train_trace_model(...)`

讓 trace learner 訓練流程也能產生 candidate target 並傳進 `train_step(...)`。

### 3. `run_p3_6g_temporal_learner.py`

新增 CLI 參數：

- `--candidate-membership-weight`
- `--candidate-top-k`
- `--candidate-secondary-scale`

並把它們寫進 `split_summary.json`。

## 第一個 focused test

輸出：

- `p3_6m22_m4b_candidate_conditioned_v1/`

測試對象：

- bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
- train window end: `43.6`
- test window: `43.7 ~ 43.9`

保留原本已知最強的 replay protocol：

- `boundary_support_start = 43.4`
- `boundary_support_repeat = 16`
- `boundary_support_positive_only = true`

新的 candidate supervision 參數：

- `candidate_membership_weight = 1.0`
- `candidate_top_k = 2`
- `candidate_secondary_scale = 2.0`

## 結果

### 主結果

- `No grouping = 0.547184178084`
- `CQI = 0.579083105194`
- `Resource-cost = 0.579083105194`
- `Multi-feature = 0.579083105194`
- `Teacher = 0.579609048805`
- `LE-GRA = 0.579083105194`

也就是說：

- `teacher > LE-GRA = CQI = resource-cost = multi-feature > no-group`

第一版沒有把 holdout 推動。

### support-side

support-side 仍然是完美的：

- `support_pairwise = 1.0`
- `support_ari = 1.0`
- `support_nmi = 1.0`
- `support_utility_gap = 0.0`

所以這次失敗不是因為：

- selector 壞了
- 或 replay 沒作用

而是：

- 即便現在加了最小版 candidate supervision
- 這個強度仍然不夠把 `m4b` 從舊 plateau 拉開

## 這一步的意義

雖然第一版結果沒有贏，但這一步仍然很有價值，因為它完成了兩件重要的事。

### 1. 我們現在有一條真正對 secondary weak candidate 下手的 supervision 路徑

以前很多修改還是在：

- pair weighting
- replay
- boundary coverage

這些比較間接的層次上調整。

現在不一樣：

- 我們已經可以顯式對 weak candidate 做 supervision

這讓下一步調整會更精準。

### 2. 第一版權重太保守，還不足以打破 `m4b` plateau

這次用的是：

- `candidate_membership_weight = 1.0`
- `secondary_scale = 2.0`

這是刻意保守的起點。

目前 evidence 表示：

- 這樣的力度還不夠

但這不代表方向錯，只代表：

- v1 還太弱

## 建議下一步

現在最合理的下一步不是重做架構，而是做很小的 calibration：

1. 提高 `candidate_membership_weight`
2. 提高 `candidate_secondary_scale`
3. 若仍然不動，再考慮把 candidate supervision 和更明確的 boundary-aware pair construction 結合

## 一句話總結

`P3.6m-22` 已經把最小版 `candidate-conditioned weak-group supervision` 實作進 learner 流程，
但在 `m4b` 上第一版保守設定還不足以推開 plateau；下一步應該做小幅度的 candidate-supervision calibration，而不是回去做 replay-only sweep。
