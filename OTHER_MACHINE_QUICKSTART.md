# 在另一台電腦接續 LE-GRA-MVP

更新日期：2026-08-24

## 資料如何攜帶

- 三個真實 Simu5G radio CSV（合計約 581 MB）由 **Git LFS** 版控。
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
```

最後一行出現以下文字，代表真實資料 hash 正確，公平比較資料也已建好：

```text
DATA_READY: real Simu5G inputs verified and requested datasets prepared.
```

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

## 第一次把本機資料發布到 GitHub

這一段只需在目前有完整 raw CSV 的電腦做一次：

```powershell
git lfs install
git add .gitattributes .gitignore
git add real_simu5g_data/raw_radio.csv real_simu5g_data/mid_raw_radio.csv real_simu5g_data/high_raw_radio.csv
git add real_simu5g_data/recovery_manifest.json prepare_project_data.py OTHER_MACHINE_QUICKSTART.md
git commit -m "Add portable real Simu5G dataset via Git LFS"
git push origin main
```

提交前可用以下命令確認三個 CSV 都列在 LFS 清單：

```powershell
git lfs ls-files
```

注意：目前工作目錄還有其他研究進度檔案；正式 commit 前應先用 `git status`
檢查，依主題分開提交，不要直接 `git add .`。
