# 覆蓋 GitHub 部署

建議使用 GitHub Desktop 或 Git，因為網頁拖曳最容易漏掉隱藏的 `.github`。

```bash
git clone https://github.com/flyree140/GPT_stocklab.git
cd GPT_stocklab
git checkout -b backup-v15
git push -u origin backup-v15
git checkout main
```

保留 `.git`，把其他舊檔移走，再把本包解壓後的內容放入根目錄：

```text
.github/
assets/
config/
data/
docs/
google-apps-script/
stocklab16/
tests/
index.html
requirements.txt
requirements-models.txt
```

然後：

```bash
git add -A
git commit -m "feat: StockLab 16 evidence-first"
git push origin main
```

GitHub 設定：

1. Settings → Actions → General → Workflow permissions → **Read and write permissions**。
2. Settings → Pages → Build and deployment → Source → **GitHub Actions**。
3. Actions → **Daily StockLab 16 research** → Run workflow。

網站預期：`https://flyree140.github.io/GPT_stocklab/`
