# P3.6m-8 train-evidence replay / curriculum diagnosis

## 背景

`P3.6m-5 ~ P3.6m-7` 已經連續證明：

- teacher 會在 `43.7s ~ 43.9s` 產生真正的 dual-weak split `{ue15, ue4}`
- LE-GRA 會 split，但通常只 isolate `ue15`
- 單純再加 loss、加 head、或把 k-means 拿掉，都還不夠

因此 `P3.6m-8` 的問題不再是「要不要再加一個 learner trick」，而是：

**目前 learner 到底是缺模型能力，還是其實只是缺足夠密度的 exact train evidence？**

## 先做的 evidence audit

針對目前主 regime：

- family: `0|1|15|2|3|4|5 @ gnb_1`
- bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
- 原 focused learner protocol:
  - train `<= 43.6s`
  - test `43.7s ~ 43.9s`

先直接稽核 teacher weakest-group evidence。

### 稽核結果

- `focus_train` 共 `526` 個 slice
- teacher positive-gain slice 只有 `7` 個
- teacher 真正的 dual-weak `{ue15, ue4}` slice：
  - train: `0`
  - test: `3`（`43.7`, `43.8`, `43.9`）

附近時間軸：

- `43.6s`
  - `teacher_groups = [[0,1,2,3,5,4],[15]]`
  - 只是 threshold-bridge split
- `43.7s ~ 43.9s`
  - `teacher_groups = [[0,1,2,3,5],[4,15]]`
  - 才是完整 dual-weak split

結論很明確：

**原本 focused learner 的 train/test gap，不只是一般的 temporal shift，而是 supervision target 在 `43.6 -> 43.7` 直接換型。**

## protocol 小改動

為了做 train-evidence 診斷，在 `run_p3_6g_temporal_learner.py` 加了三個 protocol knob：

- `--train-window-start`
- `--background-train-repeat`
- `--focus-train-repeat`

另外新增：

- `teacher_group_evidence_audit.csv`

它會把 focus-train / focus-test 的 teacher weakest-group signature 與 gain 寫出來，方便之後直接核對 train evidence。

## P3.6m-8 v1：只給少量 exact dual-weak evidence

### 設定

train:

- background train 全保留
- focus train = `43.7s ~ 43.8s`

test:

- `43.9s`

頛詨：

- `p3_6m8_support_train437_438_test439/`

### 結果

- LE-GRA utility 仍然沒有超過原本那條線
- teacher-imitation 仍然不是完整對齊
- 直接檢查 predicted grouping：
  - teacher: `[['0','1','2','3','5'], ['4','15']]`
  - LE-GRA: `[['15'], ['1','2','3','5','0','4']]`

解讀：

**只加入 2 個 exact dual-weak support slices，還不足以讓 learner 穩定學會把 `ue4` 拉進弱組。**

## P3.6m-8 v2：把 exact evidence replay 到和 background 同量級

### 先踩到的 protocol bug

一開始直接用 list 乘法重複 `Scenario` 物件，導致：

- 同一個 scenario object 被重複 reference
- 後續 in-place feature normalization 反覆作用在同一物件上
- 數值炸掉並產生 `NaN`

這不是研究結論，而是 protocol implementation bug。

之後修正成：

- replay 時使用 `deepcopy`
- 每個 repeated scenario 都是獨立副本

### 設定

train:

- background train repeat = `1`
- focus train = `43.7s ~ 43.8s`
- focus-train-repeat = `80`

所以有效訓練量：

- background = `150`
- focus exact dual-weak = `160`

test:

- `43.9s`

頛詨：

- `p3_6m8_support_replay80_train437_438_test439/`

### 結果

Main comparison：

- `Offline teacher = 0.579609048805`
- `LE-GRA MVP = 0.579609048805`

Teacher-imitation：

- `pairwise_accuracy = 1.0`
- `ARI = 1.0`
- `NMI = 1.0`

直接檢查 grouping：

- teacher: `[['0','1','2','3','5'], ['4','15']]`
- LE-GRA: `[['15','4'], ['0','5','3','1','2']]`

也就是說：

**當 `{ue15, ue4}` exact evidence 的密度被拉高到和 background 同量級時，LE-GRA 可以在 `43.9` holdout 完整學會 dual-weak split。**

## 目前最重要的研究結論

`P3.6m-8` 把 bottleneck 判斷往前推了一大步：

1. 目前主問題不是「一定得先重生資料集」
2. 也不是「membership head / prototype loss / k-means removal 都完全沒用」
3. 更核心的是：

**learner 是否學會 secondary weak candidate，強烈依賴 exact dual-weak train evidence 的密度與 curriculum。**

換句話說，現階段最值得優先做的不是盲目擴大實驗，而是：

- 想辦法在不污染主測試的前提下
- 更系統性地增加 / 組織 dual-weak 正樣本 evidence
- 再看 learner 能否在更合理的 holdout 上穩定泛化

## 對「要不要重生資料集」的判斷

目前結論是：

- **還不需要立刻重生整套資料集**
- 先做 dataset / curriculum design 比較合理

因為我們已經有證據顯示：

- 一旦 dual-weak evidence 密度夠，現有 learner family 並非完全學不會

真正缺的是：

- 更可控的正樣本密度設計
- 更乾淨的 support / holdout protocol
- 也許再往後才是更大量、更多 family、或真正外部資料

## 建議的下一步

最合理的 `P3.6m-9` 方向：

1. 建立「evidence density sweep」
   - 例如 replay `1 / 4 / 16 / 40 / 80`
   - 找出 LE-GRA 從只抓 `ue15` 到學會 `{ue15, ue4}` 的轉折點

2. 建立更乾淨的 support/holdout protocol
   - 例如 support 用 `43.7, 43.8`
   - holdout 固定 `43.9`
   - 或跨 family 做 leave-one-segment-out

3. 再決定是否需要重生資料
   - 如果 evidence density sweep 顯示需要非常大量 replay 才會學會
   - 才值得往新的 synthetic family 或新的 Simu5G/SUMO segment 擴
