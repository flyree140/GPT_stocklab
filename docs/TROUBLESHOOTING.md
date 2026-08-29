# 疑難排解

## 首頁顯示無法載入 `data/latest.json`

不要直接雙擊 `index.html`。執行：

```bash
python -m http.server 8000
```

再開啟 `http://localhost:8000`。

## GitHub Pages 是 404

- Repository 必須是 public，或你的方案必須支援私有 Pages。
- Settings → Pages 的 Source 選 GitHub Actions。
- 確認 `.github/workflows/pages.yml` 已提交。
- 查看 Actions 的 Deploy GitHub Pages 工作是否成功。

## 每日 Action 無法 push

Settings → Actions → General → Workflow permissions 允許 Read and write；Repository rules 也可能阻擋 bot 直接 push main。

更嚴格的 Repository 可改成：讓 Action 建立 Pull Request，而不是直接 push。

## 模型下載太慢或記憶體不足

手動 Run workflow 時勾選 `skip_qwen`，或設定：

```yaml
ENABLE_QWEN: "0"
```

財經情緒模型也無法使用時，程式會自動用規則，不會中止整套網站。

## 新聞為空

- 公司 Query 可能太嚴格，修改 `config/stocks.json` aliases/query。
- GDELT 或 RSS 可能暫時錯誤。
- 歷史切點很久以前時，Google News RSS 會主動跳過，只使用 GDELT。
- 關聯度低於 0.35 的文章會被捨棄。

## Google Sheets 測試失敗

- Web App 網址必須以 `/exec` 結尾，不要用 `/dev`。
- 重新部署新版本後，網址或權限可能改變。
- 確認執行過 `setup()` 與 `setSyncPassword(...)`。
- 網頁設定中的同步金鑰必須一致。
- 檢查 Apps Script Executions 記錄。

## 歷史快照 no-leak 驗證失敗

Validator 會指出路徑。常見原因：

- 把 `actual_return` 寫入 snapshot。
- 某則新聞 `available_at` 晚於 `as_of`。
- 歷史價格包含切點後日期。
- 把 result 整包嵌入 snapshot。

事後答案應只寫入 `data/results/YYYY-MM-DD.json`。
