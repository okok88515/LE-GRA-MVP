# P3.6e-1 實作說明

更新日期：2026-08-06

## 這版做了什麼

P3.6e-1 先不碰 learner，也不碰 quality controller，先直接改 coupled scenario 的資料 regime：

- 建立新的平行場景目錄 `p3_6e_coupled_scenario/`
- 建立新的 gNB 幾何 `p3_6e_gnbs.csv`
- 建立新的執行腳本 `p3_6e_run_split_pressure_coupled.sh`
- 建立新的 bundle builder `build_p3_6e_coupled_bundle.py`

## 你剛剛那個判斷對不對

部分是對的。

目前 P3.6d 的 audit 顯示：

- `distance_mean_m` 中位數大約 `101.5m`
- 很多 snapshots 的 `resource_cost_range = 0.0`
- 許多案例 CQI 已經接近或直接飽和在高值

所以問題不是單純「半徑太小」這一句話而已，
而是：

- gNB 幾何太容易讓車流停在強覆蓋區
- 車流交會位置太容易落在雙邊都很好的地方
- 發車時窗讓很多 UE 同時進入的是「都不難服務」的 regime

這會讓 offline teacher 很難真正得到 split grouping 的收益。

## P3.6e-1 的改法

### 1. 更偏邊界的雙 gNB 幾何

從：

- `gnb_1 = (200, 80)`
- `gnb_2 = (200, 320)`

改成：

- `gnb_1 = (140, 120)`
- `gnb_2 = (320, 280)`

重點不是單純拉遠，而是打破原本太整齊的上下對稱，
讓交會區更容易同時出現 center-user 與 edge-user。

### 2. 更密集的 overlap

從 24 台車改成 32 台車，四個方向各 8 台，
並把主要 depart window 壓縮到 `0.0s ~ 1.5s`。

目的：

- 讓更多 UE 在同一時段穿越中心區
- 提高 learner-facing snapshots 中 `4+ users` 的密度

### 3. 更異質的速度型態

加入三種車型：

- `slow`
- `commuter`
- `fast`

即使路線一樣，也不會完全同步通過中心區，
比較容易形成同一 snapshot 內的距離差與 handover 差。

### 4. 稍微收緊覆蓋

從：

- `ueTxPower = 20dBm`
- `eNodeBTxPower = 30dBm`

改成：

- `ueTxPower = 18dBm`
- `eNodeBTxPower = 26dBm`

這是刻意做的溫和收縮，不是要把系統弄壞，
而是避免 UE 太容易全部待在高 CQI 強覆蓋區。

## 下一步怎麼跑

### 1. 跑 P3.6e-1 coupled simulation

```powershell
wsl -d LE-GRA-opp-env -- bash --noprofile --norc -lc "cd /c/Users/Weber/Documents/LE-GRA-MVP && tr -d '\r' < p3_6e_run_split_pressure_coupled.sh | bash"
```

### 2. 建 bundle

```powershell
& C:\Users\Weber\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -u .\build_p3_6e_coupled_bundle.py
```

### 3. 跑 coupled-data audit

```powershell
& C:\Users\Weber\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -u .\audit_coupled_trace.py --bundle-dir .\p3_6e_coupled_bundle --out-dir .\p3_6e_coupled_audit
```

### 4. 跑 teacher-decision audit

```powershell
& C:\Users\Weber\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -u .\run_p3_6_teacher_decision_audit.py --bundle-dir .\p3_6e_coupled_bundle\bundle --out-dir .\p3_6e_teacher_audit
```

## 這版最想觀察什麼

這一版不是要直接把 learner 做贏，而是要先看：

- `multi_group_ratio` 有沒有從接近 0 開始上升
- `positive_gain_count` 有沒有從 0 變成真正大於 0
- learner test split 是否開始出現 `teacher_group_count > 1`

如果這版還是幾乎全單群組，那下一步就不是再亂改路線，
而是進 `P3.6e-2`，用更緊的 bundle-side `rb_budget_ratio` 去補資源壓力。
