# Google Sheets 我的最愛同步（免費）

1. 建立一份空白 Google 試算表，例如「StockLab Favorites」。
2. 在試算表開啟 **擴充功能 → Apps Script**。
3. 刪除預設程式，把 `Code.gs` 全部貼上並儲存。
4. 在 Apps Script 上方函式選單執行 `setup()`；第一次需要授權。
5. 在編輯器最下方暫時加入一行並執行，或直接在函式內呼叫：

```javascript
setSyncPassword('請換成至少 10 字元的隨機同步金鑰');
```

執行後把這一行刪掉。不要使用 Google 帳號密碼。

6. 按 **部署 → 新增部署 → 網頁應用程式**：
   - 執行身分：我
   - 誰可以存取：任何人（包含匿名使用者）或「任何知道連結的人」，依介面顯示為準
7. 複製以 `/exec` 結尾的 Web App 網址。
8. 開啟 StockLab 網站的 **設定** 頁，貼上網址、同步群組名稱與同一組同步金鑰。
9. 按「儲存並測試」。

## 資料如何保存

`Favorites` 工作表欄位為：`user_key`、`symbol`、`name`、`note`、`created_at`、`updated_at`、`deleted`。
移除最愛時採軟刪除，方便日後查核。 同步時會讀取軟刪除標記與更新時間，因此另一台裝置移除的項目也能正確消失；離線新增、移除與備註則會在下次連線時補同步。前端同時保留 `localStorage`，即使 Apps Script 暫時無法使用也不會丟失本機資料。

## 安全限制

這是低敏感度、個人書籤用途的免費同步方案，不是完整帳號與權限系統。JSONP 請求會把同步金鑰當作網址參數送出，因此：

- 只保存股票代號、名稱與非敏感備註。
- 使用專用的長隨機金鑰，不要重複使用其他服務的密碼。
- 不要把 Apps Script `/exec` 網址、同步群組與金鑰一起公開。
- 需要公開多人服務時，改用 Firebase Authentication、Cloudflare Workers 或正式後端。
