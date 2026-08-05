# P3.6 下一步：Coupled Data Quality 與真實 QoE

更新日期：2026-08-06

## 目前所在位置

P3.0–P3.5 已把資料路徑從 synthetic generator 推進到真正同時執行的
SUMO+Veins+Simu5G：schema、SUMO mobility、Simu5G per-band radio、stable ID、共同
timestamp、P3.2 join、P3.0 loader 與 offline teacher 都已通過。

現在的瓶頸不再是「資料能不能進 learner」，而是「進去的 coupled data 是否具有
足夠研究資訊」。目前 6 秒 smoke trace 只有 2 台車、CQI 全為 15，且
`previous_quality=3` 是控制值，因此不可直接拿來宣稱 real-trace learner 成果。

## P3.6 優先順序

### P3.6a：建立 informative coupled scenario

先以小型、可快速重跑的設定增加 channel variation：

1. 延長官方 route 到足以同時出現多台車，但先不做多 seeds。
2. 調整 gNB/route 幾何，使 UE 覆蓋近、中、遠距離。
3. 加入 background/inter-cell interference 或遮蔽設定。
4. 保留 dynamic association/handover，確認 serving gNB 真的可能改變。
5. 每次只改一組因素，跑完立刻做 audit。

不要先跑 learner。先回答下列資料問題：

- 同時在線 UE 數是否足以形成 grouping？
- CQI 是否不再飽和於 15？
- 同一 UE 是否有 per-band TBS dispersion？
- 是否存在 wideband CQI 相近、但 RB profile 不同的 ambiguous pairs？
- 是否出現 serving-cell change 或 handover？

### P3.6b：加入 video application state recorder

找出 Simu5G video/streaming application 的 representation、bitrate、buffer 或 playback
state。`previous_quality` 必須來自同一 coupled simulation 的 app state，並記錄：

- recorder 的 module path 與 signal/source；
- timestamp 與 UE ID mapping；
- representation index 到 bitrate 的對應；
- startup/warm-up、stall、missing state 的處理；
- 不允許以固定值或隨機值補缺。

如果官方 app 沒有適合的 adaptive video state，先建立最小 deterministic adaptation
controller，輸入必須是 simulation 中的 throughput/buffer state，輸出 quality index；
不可直接用 CQI 推回 quality，否則會造成 feature leakage。

### P3.6c：建立 coupled-data audit

建議新增一個獨立 audit CSV/報告，至少包含：

- snapshots、active UEs、serving gNB/handover counts；
- CQI min/median/max、unique values、saturation ratio；
- per-UE/per-band TBS mean/std/range；
- wideband-similar/RB-profile-different ambiguous pair ratio；
- RB budget/resource pressure distribution；
- previous quality distribution、switch count、stall/missing ratio；
- join exclusions與原因。

## 第一階段 acceptance gate

在開始 learner real-trace experiment 前，至少要看到：

1. 多個 snapshots 有 5 個以上同 serving-gNB UEs。
2. CQI 不全為 15，且有多個非飽和值。
3. 有非零 per-band TBS dispersion。
4. 能量化至少一些 ambiguous user pairs，而非只靠場景名稱宣稱 ambiguous。
5. `previous_quality_source` 不再是 experiment control。
6. P3.2 join、P3.0 load、offline teacher 仍全部通過。

這些門檻是資料完整性 gate，不是論文最終統計門檻；先用一個 seed、小規模場景
證明值得擴大，再決定 seeds、duration、Kmax 與矩陣規模。

## 建議明日第一個實作

先新增 `audit_coupled_trace.py`，對目前 P3.5 bundle 建立 baseline audit，明確輸出
「CQI saturation=100%、無 informative ambiguity」。接著只修改一個小型 coupled
scenario 參數組合，重新執行同一 audit。這能讓後續場景調整有量化依據，也可避免
為了得到好看的 learner 結果而無方向地調 simulator。

## 不應優先做的事

- 不擴大 Kmax、seeds 或 standard matrix。
- 不把 P3.5 all-CQI-15 trace拿去訓練並解讀 learner ranking。
- 不用 random/synthetic value 填補 video quality。
- 不用 realized scheduler throughput 取代 counterfactual per-band TBS。
- 不以 module index 猜 SUMO ID；繼續使用 module-path mapping。
