# 在另一台電腦接續 LE-GRA-MVP

更新日期：2026-08-25

## 資料如何攜帶

- 三個真實 Simu5G radio CSV（合計約 581 MB）由 **Git LFS** 版控。
- protocol-v3 multi-seed archive（30 runs、60 個 `.csv.gz`、約 403 MB）
  也由 **Git LFS** 版控。
- 三個 mobility CSV、場景設定、驗證結果與資料 provenance 直接放在 Git。
- `fair_input_dataset_v1/` 約 61.8 MB，但可由固定 seeds 完整重建，因此不提交。

這樣能保留不可取代的真實模擬輸入，也不會把大量可重建的 NumPy shards
塞進 Git history。

## 第一次設定

先安裝：

1. Git
2. [Git LFS](https://git-lfs.com/)
3. Python 3.10 以上
4. Python 套件：`numpy`、`scikit-learn`、`torch`

接著執行：

```powershell
git clone git@github.com:okok88515/LE-GRA-MVP.git
cd LE-GRA-MVP
python -m pip install numpy scikit-learn torch
python .\prepare_project_data.py
python .\validate_real_simu5g_multiseed.py
```

最後一行出現以下文字，代表真實資料 hash 正確，公平比較資料也已建好：

```text
DATA_READY: real Simu5G inputs verified and requested datasets prepared.
```

接著 multi-seed validator 最後應出現：

```text
MULTISEED_QA_PASS runs=30 scenarios=450
```

完整 validator 會解析全部 30 runs，因此需要數分鐘。

## 每天開始工作

```powershell
git pull
python .\prepare_project_data.py
```

腳本發現 `fair_input_dataset_v1/manifest.json` 已存在時不會重建，只會驗證。

只想快速確認真實資料、不建公平資料：

```powershell
python .\prepare_project_data.py --skip-fair
```

資料已經在本機、暫時不想連 Git LFS：

```powershell
python .\prepare_project_data.py --skip-lfs --skip-fair
```

要強制重建公平資料：

```powershell
python .\prepare_project_data.py --rebuild-fair
```

## 目前已發布的資料版本

截至 2026-08-25，資料與 runner 已推送到 `origin/main`：

- `4dd6dd2`：protocol-v3 multi-seed runner 與 QA
- `9906a6e`：10 seeds × 3 dispersions 的正式資料

可用以下命令確認 LFS 檔案已完整下載：

```powershell
git lfs ls-files
```

## 明天第一個工作項目

閱讀 `SESSION_HANDOFF.md` 最上方的 2026-08-25 authoritative handoff，然後
建立 `run_real_multiseed_baseline.py`。先比較 CQI、resource-cost、
multi-feature 三種不用學習的方法；以 simulation seed 為統計單位，不可把
同一 run 的 15 個相鄰 snapshots 當成獨立樣本。

注意：三個 legacy mobility CSV 在 Windows 可能因換行偵測顯示 `M`，但內容
hash 與 Git 版本相同，不要把這三個 false-positive 修改提交。
