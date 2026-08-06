# P3.6a Informative Coupled Scenario

更新日期：2026-08-06

## 為什麼要做這個場景

P3.5 的 coupled smoke test 已經證明：

- SUMO mobility 可以進來
- Simu5G radio 可以匯出
- P3.2 join 可以成功
- offline teacher 可以在真實 trace bundle 上運作

但它還不是 learner-ready 的資料，因為當時的 trace 有幾個問題：

- 多 UE snapshot 太少
- CQI 幾乎全部都是 15
- per-band profile 幾乎沒有變化
- 沒有 ambiguous pair
- 沒有 handover

所以 P3.6a 的目標，不是多跑幾組實驗，而是先設計一個更「有資訊量」的 coupled scenario。

## 設計目標

新的 informative scenario 要刻意創造以下條件：

1. 同一時間要有多個 UE 同時在線
2. UE 要跨越兩個 gNB 的覆蓋交界，讓 handover 有機會發生
3. 不能讓所有 user 永遠 CQI=15
4. 25-band profile 要有可觀察的頻域差異
5. 要出現同 CQI 但不同 RB profile 的 ambiguous pair

## 實作內容

### 1. 新的 gNB 位置

檔案：`p3_6_gnbs.csv`

- `gnb_1 = (200, 80)`
- `gnb_2 = (200, 320)`

這樣的配置會讓道路中央附近形成更明顯的 serving-cell 交界。

### 2. 更密集的車流

檔案：`p3_6_coupled_scenario/heterogeneous.rou.xml`

- 總車數：24
- 路線數：4
- departure time 集中在 `0.0s` 到 `4.2s`

這樣可以把原本太稀疏的車流，變成長時間的 multi-UE overlap。

### 3. 更長的模擬時間

檔案：`p3_6_coupled_scenario/omnetpp.ini`

- `sim-time-limit = 35s`

P3.5 smoke 只看很短的時間窗，很多車根本還沒進場。  
拉長到 35 秒後，才有足夠機會觀察：

- 多 UE 同時活動
- CQI 變化
- serving gNB 切換
- coupled recorder 的長時序輸出

### 4. 降低過度飽和

同樣在 `omnetpp.ini` 裡：

- `eNodeBTxPower = 30dBm`
- `ueTxPower = 20dBm`

這樣做的目的不是故意把系統弄差，而是避免所有 user 都被推到完全飽和區，讓 CQI 與 per-band TBS 保留差異。

### 5. 下行流量設定

`[Config P3_6_Informative_DL]`

- `server.numApps = 24`
- 每台車都有對應的 downlink VoIP sender

這讓每個 UE 都更有機會被 scheduler 真正觸發出有效 feedback，而不是只有少數 UE 活躍。

## 執行流程

### 1. 先確認環境

```powershell
wsl -d LE-GRA-opp-env -- bash --noprofile --norc -lc "cd /c/Users/Weber/Documents/LE-GRA-MVP && tr -d '\r' < p3_5_check_environment.sh | bash"
```

### 2. 安裝或修正 recorder

```powershell
wsl -d LE-GRA-opp-env -- bash --noprofile --norc -lc "cd /c/Users/Weber/Documents/LE-GRA-MVP && tr -d '\r' < p3_5_apply_recorders.sh | bash"
```

### 3. 跑 informative coupled scenario

```powershell
wsl -d LE-GRA-opp-env -- bash --noprofile --norc -lc "cd /c/Users/Weber/Documents/LE-GRA-MVP && tr -d '\r' < p3_6_run_informative_coupled.sh | bash"
```

### 4. 建 bundle

```powershell
wsl -d LE-GRA-opp-env -- bash --noprofile --norc -lc "source /home/opp_env/.venv/bin/activate && cd /c/Users/Weber/Documents/LE-GRA-MVP && python3 build_p3_6_coupled_bundle.py"
```

### 5. 跑 audit

```powershell
wsl -d LE-GRA-opp-env -- bash --noprofile --norc -lc "source /home/opp_env/.venv/bin/activate && cd /c/Users/Weber/Documents/LE-GRA-MVP && python3 audit_coupled_trace.py --bundle-dir ./p3_6_coupled_bundle --out-dir ./p3_6_coupled_audit"
```

## 本次實際產出

### Raw coupled output

- `p3_6_coupled_output/raw_radio.csv`：1,045,526 行
- `p3_6_coupled_output/raw_mobility.csv`：2,510 行

### Coupled bundle

- `sumo_vehicles = 10`
- `radio_user_rows = 2503`
- `bundle_scenarios = 657`
- `teacher_scenarios = 657`

## 這個場景解決了什麼

和 P3.5 smoke 相比，P3.6a 已經成功把資料推進到更像研究資料，而不是單純 integration artifact：

- multi-UE snapshots 從極少量提升到 614
- CQI 不再只有單一值
- per-band rate profile 出現明顯 dispersion
- ambiguous pairs 大量出現
- handover 開始出現

也就是說，P3.6a 已經把 coupled trace 的「無聊場景」變成「有辨識價值的場景」。

## 仍然留下的缺口

P3.6a 還沒有完成的，不在 radio / mobility，而在 quality state：

- `previous_quality` 仍然是固定控制值
- `quality_switch_count = 0`
- 還不能說這份 trace 已經包含真實的 adaptive video state

所以 P3.6a 的定位是：

> 把 coupled trace 的 channel / mobility / handover 資訊先做出來，  
> 讓後續 P3.6b 可以專心補 measured previous quality。
