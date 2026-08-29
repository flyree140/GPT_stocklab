# 先從這裡開始：StockLab Free AI v14

這一包已包含網站、每日新聞分析、免費 Hugging Face 模型設定、每日置頂、傳統分析、Google Sheets 我的最愛、歷史無洩漏驗證、GitHub Actions、Kaggle 回填 Notebook、測試與完整簡報。

## 最快上線流程

1. 解壓 ZIP，確認 `.github/workflows/` 沒有被漏掉。
2. 在 GitHub 建立 **Public Repository**，把解壓後資料夾內的所有內容上傳到 Repository 根目錄。
3. 到 **Settings → Pages**，Source 選 **GitHub Actions**。
4. 到 **Settings → Actions → General → Workflow permissions**，允許 Read and write permissions。
5. 到 **Actions → Daily free news analysis → Run workflow**，先手動執行一次。
6. 等工作流程完成後，**Deploy GitHub Pages** 會接續部署最新資料。

目前 `data/latest.json` 是清楚標示的合成示範資料；第一次每日工作流程成功後，才會由真實免費來源取代。

## Google Sheets 我的最愛

1. 建立空白 Google Sheet。
2. 開啟 **擴充功能 → Apps Script**。
3. 貼上 `google-apps-script/Code.gs`。
4. 執行 `setup()`，再執行 `setSyncPassword('至少 10 字元的專用隨機金鑰')`。
5. 部署為 Web App，把 `/exec` 網址與同一組金鑰填入 StockLab 的「同步設定」。

同步先寫本機，再與 Google Sheet 依更新時間及軟刪除標記合併；離線加入、移除或備註會在下一次連線補同步。這是個人、低敏感度書籤方案，不是正式會員系統。

## 重要文件

- `README.md`：功能總覽與本機執行
- `docs/DEPLOY_GITHUB.md`：完整 GitHub 部署
- `docs/MIGRATE_FROM_OLD_STOCKLAB.md`：更新既有 flyree140/stocklab
- `google-apps-script/SETUP.md`：Google Sheets 設定
- `docs/NO_LEAK_VALIDATION.md`：歷史驗證與防偷看未來
- `StockLab-Free-AI-v14-完整簡報.pptx`：可編輯簡報
- `StockLab-Free-AI-v14-完整簡報.pdf`：簡報 PDF

## 免費模式的邊界

不需要付費 LLM API。公開 GitHub Repository 使用標準 GitHub-hosted runner 與 GitHub Pages 時，可在平台免費政策內運作；模型、資料端點、Actions cache、Apps Script 與 Kaggle 仍有各自配額、限流、執行時間及條款。模型下載或推論失敗時，程式會降級到透明規則，不會直接讓網站停止更新。

本工具只用於研究與驗證，不構成投資建議。
