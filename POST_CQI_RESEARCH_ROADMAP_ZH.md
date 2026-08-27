# 超越 CQI k-means 的三條研究方向（加一條規模驗證）

更新日期：2026-08-26

## 研究目標與共同規則

目標不是減少計算量，而是找出 CQI k-means 原理上看不到、且能穩定
轉化成 utility 增益的資訊。三條方向都要走，但先分開驗證機制，最後
才考慮整合成一個動態 compatibility graph。

所有比較固定使用：

- 相同的 real Simu5G snapshots、load、RB budget 與 `Kmax`
- 相同的 exact-DP allocation
- 相同 utility：normalized log bitrate 減去 `0.5 ×` normalized quality
  switching magnitude；unserved penalty 不變
- simulator seed/trajectory 為統計獨立單位
- 同一實驗宣告的輸入變數要對所有競爭方法開放；差異應來自分群法，
  不能只讓新方法偷看額外變數
- published CQI k-means 保留為歷史 anchor；另加「相同新輸入 + k-means」
  作為真正隔離演算法效果的公平 baseline
- 所有 threshold、horizon、graph hyperparameter 只可由 training seeds
  選擇，test seeds 不得回頭調參

## 方向一：同 CQI、不同頻率選擇性 —— 2026-08-26 初步驗證完成，詳見 `REAL_SIMU5G_RB_PROFILE_DIRECTION.md`

**結論摘要(完整結果、機制診斷、歸因分析見獨立文件)**：full-profile/block-profile
k-means、overlap graph 三個方法都沒有通過go/no-go標準，予以放棄。exact-regret
graph 一開始因為漏掉RB可行性檢查而慘敗(尤其high×heavy)，修好bug後在
**high離散度+heavy負載**這個資源最稀缺的極端情境下有真正、機制清楚的增益
(10 seed exploratory：8~10/10 seed贏)，且已整合成`cqi_cost_regret_graph_hybrid_grouping`
(CQI∪cost∪regret-graph 3-way聯集)，在9格裡沒有任何一格輸給既有的2-way聯集，
high×heavy的增益幅度更幾乎翻倍(+0.0416→+0.0846)。**目前仍是10-seed exploratory
規模，尚未做confirmatory驗證**——seeds 11-30已經被switching gate用掉，若要confirm
這個3rd候選家族，需要另外的新seed range。

### 遺失的資訊

兩名使用者可以有相同 wideband CQI，但每個 RB 的通道形狀不同。一人
可能在多數 RB 上穩定，另一人只有少數 RB 很好；若兩人的好 RB 位置
不重疊，multicast 同組後會產生 bottleneck。CQI k-means 看不到這個
差異。

現有 multi-feature 只把 RB rate 壓成 mean/min/max/std，也會丟掉
「好 RB 出現在哪裡」以及兩名使用者好 RB 是否重疊的資訊。resource-
cost vector 則只回答單一使用者需要多少 RB，沒有直接回答兩人是否
適合同組。

核心假設：

> Wideband CQI 無法描述使用者間的頻域相容性；multicast grouping
> 應根據 pairwise RB-profile compatibility，而不是單一使用者的
> scalar channel quality。

### 要測的方法

1. 保留完整 25-band RB-rate profile，或先壓成少數連續頻域區塊。
2. 定義 pairwise overlap，例如 normalized overlap、cosine/correlation、
   共同高效率 RB 比例，以及兩人同組造成的 exact utility regret。
3. 由 pairwise compatibility 建 user graph。
4. 比較 spectral clustering、correlation clustering、graph partitioning
   與 constrained agglomerative merging。

### 公平基線與主要 ablation

- CQI k-means：published anchor
- resource-cost k-means：scalar/vector cost baseline
- full RB-profile k-means：使用完全相同的 25-band input，隔離「資訊」與
  「graph algorithm」的效果
- block-profile k-means：確認完整頻域位置是否真的必要
- overlap graph without utility regret：確認簡單相似度是否已足夠
- exact-regret graph：檢驗 utility-aware edge 是否是主要來源

### Go/no-go 證據

- 在 matched/similar CQI pairs 中，RB-profile overlap 能預測 teacher
  split 或同組 regret
- graph method 在 seed-level paired utility 上勝過 full-profile k-means，
  才能聲稱是 compatibility graph 的貢獻，而不只是多看了特徵
- 增益應集中於 mid/high dispersion，並能由 bottleneck RB 或 served
  ratio 的改變解釋

## 方向二：同 CQI、不同 QoE switching state — 2026-08-26 confirmatory驗證完成，詳見 REAL_SIMU5G_REGRET_GRAPH_TEMPORAL_DIRECTION.md

方向一驗證出的 exact-utility-regret graph，其 regret 公式本來就包含
`group_quality_value` 對 `previous_quality` 的 switching penalty；方向一
自己的評估用的是 snapshot-level scenario(`previous_quality`全部歸零)，
從未真正測過這一項。把同一個 regret graph 拿去跑 real temporal closed
loop(`previous_quality`真的會因為使用者而分化)，10-seed exploratory結果
一度顯示`CQI+cost+regret-graph 3-way union`(不含switching)在每一格都至少
追平、high dispersion三格明確贏過`CQI+cost+switching 3-way union`
headline，一度以為switching可以拿掉。

**用20個全新seed(31-50)confirmatory驗證後，結論修正了**：regret-graph
單獨拿掉switching，在mid dispersion其實有不小比例會輸給switching
headline(mid/light 7/20、mid/medium 8/20敗)，小樣本的exploratory沒完整
呈現這件事——**switching不該拿掉**。但confirmatory證據強烈支持另一件事：
把switching跟regret-graph**一起**疊加成4-way union，在20個新seed的6個
非飽和格子裡對現有switching headline**零敗場**，且5/6格達到統計顯著
(含全部3個high dispersion格)。這正是候選聯集"只會更好、不會更差"的
guarantee在confirmatory規模下確實成立——4-way union已成為新的建議
headline，取代原本的switching-only 3-way。

### 遺失的資訊

兩名當前 CQI 相同的使用者，前一時刻可能分別處於高、低畫質。強迫
兩人選同一 group quality，可能讓其中一人承擔較大 switching loss。
CQI k-means 完全看不到這個狀態；把 `previous_quality` 當作 joint
k-means 的另一個座標，也不等於學到 switching penalty 的非線性影響。

目前的 real closed-loop attribution 已提供初步證據：

- switching candidate 在 mid/high 840 transitions 中只嚴格勝出 60 次
- `previous_quality_std` 是最強的 regime feature
- previous quality 幾乎同質的 404 transitions 中沒有 strict win
- top heterogeneity quartile 的 strict-win rate 為 20.2%

這證明狀態異質性有訊號，但還沒有驗證真正的 pairwise regret graph。

### Pairwise regret 定義

對候選 pair 定義：

\[
R_{ij}=U_i^{\mathrm{separate}}+U_j^{\mathrm{separate}}
      -U_{ij}^{\mathrm{same\ group}}
\]

此 regret 應在同一 decision state、相同 load 與 RB budget 下計算或近似，
自然包含：

- CQI bottleneck
- RB cost
- previous quality
- switching penalty
- 當下 load

核心假設：

> 當 CQI 相同時，previous-quality divergence 可以預測 utility-aware
> teacher split，而且該 split 的增益不是單純由 CQI 或 resource cost
> 解釋。

### 要測的方法

1. 先以 exact two-user regret 建 oracle/diagnostic graph。
2. 再用可部署的解析近似或小模型預測 `R_ij`，不要直接模仿 teacher
   group label。
3. 對 regret graph 做 min-cut、spectral/correlation clustering，或受
   `Kmax` 限制的 agglomerative merging。
4. 分開測 channel-only regret、channel+previous-quality regret，以及
   完整 load-aware regret。

### 公平基線與主要 ablation

- `[CQI, previous_quality]` k-means
- 相同 regret-derived pair features 的一般 k-means/embedding baseline
- always-on 3-way switching candidate
- fixed `eta=.020` conditional candidate gate
- exact regret graph 與 learned regret graph

只有 learned/graph method 勝過使用相同輸入的 joint k-means，才可把
增益歸因於 pairwise objective，而不只是加入 `previous_quality`。

## 方向三：短期趨勢與多時槽 utility — 2026-08-26 Step 1初步驗證完成，詳見 REAL_SIMU5G_TREND_DIRECTION.md

Step 1(causal hand-crafted trend baseline)結果：單獨用slope/volatility/
downside-deviation分組，比CQI k-means明顯更差(high/heavy dCQI=-0.094)——
trend資訊完全丟掉當下通道品質，不能單獨用。跟CQI union後拉回持平，
high/heavy有真實增益(+0.027)。疊加在方向二confirmatory驗證過的4-way base
上，每一格零敗場(snapshot-level，union guarantee精確成立)，但增益很小
(最大+0.0046)，且集中在regret-graph、resource-cost本身就很強的high/heavy
情境——推測trend抓到的是類似訊號的提早預警，不是全新的正交資訊。暫不
建議納入headline；Step 2(predictor)、Step 3(多時槽objective)才更可能
榨出trend的真正價值。

### 遺失的資訊

兩名使用者當前都是 CQI 8，但一人可能由 `[4,5,6,7,8]` 持續改善，
另一人由 `[12,11,10,9,8]` 持續惡化。snapshot CQI k-means 視為完全
相同；一般 contrastive learning 即使看見五步 history，也不保證會
學到「未來方向相反」對 switching 與 group persistence 的重要性。

核心假設：

> Grouping 不應只最佳化單一 snapshot，而應最佳化未來 `H` 個時槽的
> 累積 utility；history 只有在 objective 獎勵未來穩定性時才會持續
> 產生價值。

### 顯式時間特徵

- CQI slope
- recent-window volatility、minimum 與 downside deviation
- outage probability
- 預測下一時刻 CQI 或 RB profile
- previous group membership、group age 與 regrouping cost
- trend disagreement between candidate group members

### 要測的方法

1. 先做 causal hand-crafted trend baseline：只用當下以前資料。
2. 建一個 next-step predictor，並明確和使用真實 future CQI 的 oracle
   lookahead upper bound 分開報告。
3. 將 teacher objective 改為

\[
\max_{g_{t:t+H-1}}
\sum_{h=0}^{H-1}\gamma^h U_{t+h}
-\lambda_g C_{\mathrm{regroup}}
\]

4. 比較 greedy snapshot、minimum-margin gate、one-step lookahead 與
   windowed teacher imitation。

### 因果與公平限制

- 部署方法在時間 `t` 不得使用真實 `t+1` CQI；真實 future 只能作
  oracle ceiling
- 所有 competitor 都可使用相同五步 history 與衍生 trend features
- horizon `H`、discount `gamma`、regrouping penalty 只能用 training
  seeds 選擇
- train/test 必須按 simulator seed 切分，不能把相鄰 snapshots 分到
  不同 split

## 方向四（規模驗證，非資訊缺口）：真實資料的使用者規模 — 2026-08-27 已定案N=40，詳見 REAL_SIMU5G_SCALE_PILOT.md

**最終結果跟一開始的Phase 1判斷不一樣，重要更正**：路網用`netgenerate`
重新產生、headless SUMO驗證都順利，一度以為100台車可行。但實際跑真實
OMNeT++/Simu5G後，同時在線峰值只有54/100——headless SUMO的預測完全不準。
診斷發現真正瓶頸是**Veins/TraCI的車輛attach機制在高負載下有複合式延遲**
(不是路網或mobility問題)：越晚該進場的車，延遲越嚴重且是複合增長；反直覺
的是，把發車間隔拉緊反而更糟(congestion加劇)，拉鬆才有幫助——證實這是
「排隊等attach」而非「插入時起步太慢」。

**另一層限制**：專案既有的`parse_real_simu5g_data.py`要求「固定編號
0~N-1的封閉人口」連續5秒都有完整覆蓋(這也是方向二temporal closed-loop
追蹤`previous_quality`所需要的前提)。這比「任意N人重疊」的分析嚴格很多，
把可行規模又往下壓。這是一個**真正的架構分岔點**，已經跟你討論並由你決定
——不改動現有資料模型(不做rolling population的重新設計，避免衝擊方向二
方法論)，接受因此變小的規模。

**最終定案**：50台車請求、發車間隔放寬到0.5秒，**N_USERS=40**作為parsing
目標——在low/mid/high三個dispersion都驗證出一致的5個可用連續5秒視窗，
確認瓶頸來自mobility/attach機制、與發射功率無關。CQI histogram跟原本
24台車比，三個dispersion都有一致、可解釋的小幅偏移(mean略降、std略升，
路網變大導致遠端使用者實際距離變遠)，你已確認接受現狀不用再校準。

**誠實面對現實**：N=40離原本「至少100」的目標有明顯落差，離論文150人的
總規模更遠(50 VU是單一service的規模，不是總數)。這點必須誠實記錄，不能
含糊。仍然比原本24台車多67%，是有意義的提升。

**同一天後續**：已經產生並QA驗證通過一批真正的10-seed multi-seed資料
(30個run)，過程中抓到並修好兩個真bug——(1)第一次批次生成時誤用了設計
反覆迭代期間留下的舊pilot殘留資料(靠比對row count抓出來，清空重跑解決)；
(2)`parse_real_simu5g_data.py`的`usable_buckets`只檢查radio完整性、
沒檢查mobility完整性，這個新規模的滾動人口設計會踩到這個洞(原本24台車
設計從未觸發過)，已修好並確認對原始資料零影響。最終30/30通過QA，147個
可用場景，CQI histogram跟單一seed pilot的發現一致。

**再往下一步**：拿這批N=40資料跑了方向一的方法比較(snapshot-level)，
詳見`REAL_SIMU5G_SCALE_PILOT_METHOD_COMPARISON.md`。結果：switching在
snapshot-level完全沒貢獻(3-way跟2-way數字一模一樣，4-way跟regret-graph
3-way一模一樣)——這是預期中的，因為`previous_quality`全部歸零，switching
本來就沒訊號可用。**regret-graph的優勢確實複製了，而且在N=40比N=24更
明顯**——high dispersion+heavy load這個regret-graph機制最該發揮的情境，
比2-way union多贏0.074、8/10 seed全勝，比N=24時的幅度更大。這剛好呼應
`dispersion-and-scale-calibration`那份合成資料的規模效應預測：使用者
越多、population裡出現極端outlier的機率越高，regret-graph的機制正好
是抓這種outlier的，N=40給了這個機制更多發揮空間。仍是10-seed exploratory。

2026-08-26 使用者提出的顧慮：目前所有真實 Simu5G 驗證(含 confirmatory
gating)都固定在 **24 台車**，這是沿用更早期 P3.6 場景設計的規模，不是
針對這次switching gating實驗特別挑選的。這跟前三個方向不同——不是
「CQI看不到的新資訊」，是「樣本規模本身夠不夠有代表性」的問題，
但同樣值得認真補上。

### 為什麼不是改個參數就能做

- 400×400公尺路網、4條路線、low/mid/high 三個離散度的基地台發射功率
  校準，全部是針對24台車的車輛密度/干擾模式調的。塞進100+台車，密度
  跟干擾模式會完全不同，現有校準會失效，等於要重新設計、重新校準一個
  新場景——不是「同一實驗、加大N」。
- 這正是本專案自己已經標記過的方法論風險（見
  `review-le-gra-methodology` memory）：迭代式重新設計場景容易變成
  p-hacking-like，必須用同樣嚴謹的預先校準(只看CQI histogram、不看
  分組結果比較)流程，跟 `p3_7_clean_validation_scenario` 當年的做法
  一致。
- OMNeT++/Simu5G 物理層模擬的wall-clock成本隨車輛數增加(非嚴格線性)，
  雖然目前24台車、90秒模擬只需約29秒，不是決定性障礙，但仍是額外
  工程量。

### 已有的間接證據（僅來自合成資料，尚未在真實物理層驗證）

見 `dispersion-and-scale-calibration` memory：合成資料上n=24/50/150/
300/500的規模效應是單調且真實的——「不分組」ADR佔最佳方法比例隨人數
增加持續下降(85.3%→65.3%→60.3%→56.0%→43.0%)，且n≥150時「不分組」的
絕對ADR會鎖死在最低畫質等級(因為大樣本幾乎必然出現至少一個極差通道
使用者)。使用者自己發表的論文本身用的規模是 **50 VU**(Section 4)，
比目前真實資料track的24台車還大——這代表24台車在真實資料track上确实
偏小，是一個誠實揭露、待補的限制，不是可以忽略的細節。

### 建議做法（尚未執行，待排入時程）

1. 先在SUMO層級單獨驗證：擴大路網/車輛數後，重新做一次跟
   `p3_7_clean_validation_scenario`當年一樣的「只看CQI histogram校準
   發射功率」流程，不看任何分組結果比較，避免針對假設調整場景。
2. 用小規模pilot(例如50台車，對齊論文自己的規模)先驗證整套pipeline
   (SUMO路網generation、per-seed patch reconstruction、QA)在新規模下
   還能跑，再決定要不要進一步推到100+。
3. 這個驗證跟方向一二三是獨立的——不需要等三個資訊缺口方向做完才開始，
   但因為是新場景/新校準工程，複雜度不小，建議排在三個資訊缺口方向
   之後，或找人力空檔時獨立推進。

## 執行順序

### Step 0：先完成已凍結的 gating confirmation

- 產生 `seed_0011..0030`
- 固定 `eta=.020`
- 不用新 seeds 重選 threshold
- 分開報 original 10-seed exploratory 與 new 20-seed confirmatory

這批新 20 seeds 是 fixed-gate 的 confirmatory set。一旦看過結果，它們
就不能再被稱為三個新方向的 untouched confirmatory set；新方向可先用
seed-level nested CV 探索，最終主張仍需另外保留新 seeds 或預先宣告的
holdout。

### Step 1：頻域相容性 —— 已完成初步(exploratory)驗證，見 `REAL_SIMU5G_RB_PROFILE_DIRECTION.md`

full-profile k-means、block-profile k-means、overlap graph 三個方法都沒通過
go/no-go標準。exact-regret graph 修好一個RB可行性檢查的bug後，在high×heavy
(資源最稀缺的極端情境)有真正、機制清楚的增益，已整合成3-way聯集
(`cqi_cost_regret_graph_hybrid_grouping`)。下一步是confirmatory驗證(需要新
seed range)，或直接推進方向二/三。

### Step 2：QoE pairwise regret —— 已完成confirmatory驗證，見 `REAL_SIMU5G_REGRET_GRAPH_TEMPORAL_DIRECTION.md`

不需另建 switching-only regret：方向一的 exact-regret graph 拿去跑真實
temporal closed loop。20-seed confirmatory驗證(seed 31-50)修正了exploratory
的初步結論——regret-graph單獨拿掉switching在mid dispersion有實質敗場，
switching不該拿掉；但switching+regret-graph的4-way union對現有switching
headline零敗場、5/6格顯著更好，已成為新建議headline。方向三現在建立在
這個4-way之上，不再用regret-only 3-way當base。

### Step 3：短期 horizon —— Step 1(causal hand-crafted baseline)已完成，見 `REAL_SIMU5G_TREND_DIRECTION.md`

Step 1結果：trend feature疊加在方向二4-way base上有小但真實的增益(最大
+0.0046，high/heavy)，零敗場，但幅度不大，且訊號可能跟regret-graph/cost
高度重疊。暫不納入headline。

先做 one-step causal predictor 與 oracle ceiling，確認未來資訊有足夠
上限；若 ceiling 本身沒有增益，就不要先投入複雜 sequence model。
若有，再建立 windowed utility teacher 與 persistence-aware grouping。

### Step 4：最後才整合

若三條 ablation 各自成立，最終可建立 dynamic compatibility graph：

```text
edge(i,j,t) = predicted cumulative same-group regret over horizon H
```

edge 同時使用 RB-profile overlap、previous-quality divergence、load 與
CQI trend，再由 graph partitioner 在 `Kmax` 約束下分群。整合模型必須
和每條單獨方向做 ablation，避免只得到一個難以解釋的 feature soup。
