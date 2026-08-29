# Google Sheets 我的最愛設計

## 為什麼選 Apps Script

GitHub Pages 只能提供靜態檔，不能直接把每位使用者的最愛寫回 Repository。Google Apps Script 可以將個人的低敏感度書籤寫入自己的 Google Sheet，且不需要常駐伺服器。

## 雙層保存

1. 使用者操作先寫入 `localStorage`。
2. 加入、備註與移除都保留 `updated_at`；移除另存本機 tombstone。
3. 若已設定 Apps Script，前端再同步雲端。
4. 雲端錯誤不刪除本機資料。
5. 下次同步會讀取 active items 與軟刪除標記，依更新時間合併；另一台裝置的移除與本機離線操作都能補同步。

## API 動作

- `ping`
- `list`（可選 `include_deleted=1` 取得同步用軟刪除標記）
- `add`
- `remove`

使用 JSONP 是為了讓純 GitHub Pages 能讀 Apps Script ContentService；因此同步金鑰會成為 request URL 的 bearer credential。它只適合股票書籤，不適合敏感資料。

## 工作表欄位

| 欄位 | 說明 |
|---|---|
| user_key | 自訂同步群組，多裝置填同一值 |
| symbol | 股票代號 |
| name | 股票名稱 |
| note | 個人備註，最多 500 字 |
| created_at | 第一次加入 |
| updated_at | 最後修改 |
| deleted | 軟刪除 |

## 基本防護

- 同步金鑰在 Apps Script properties 中只保存 SHA-256。
- callback 名稱白名單，降低 JSONP 注入風險。
- 使用 LockService 避免同時寫入衝突。
- 文字欄位限制長度並防止試算表公式注入。
- 每一同步群組最多 100 個 active favorites。

## 何時該升級

以下情況不要再用這個簡化方案：

- 需要公開多人註冊與登入
- 儲存個資、交易紀錄或其他敏感資料
- 需要細緻權限、稽核與刪除請求
- 大量同步或商業服務

可改用 Firebase Authentication + Firestore、Supabase Auth 或 Cloudflare Workers + D1。

## 瀏覽器端資料

- `stocklab.free.favorites.v2`：目前有效的最愛。
- `stocklab.free.favorite-tombstones.v1`：離線移除記錄，最多保留 200 筆並清除超過 180 天的項目。
- `stocklab.free.settings.v2`：Apps Script 網址、同步群組、專用同步金鑰與自動同步選項。

同步金鑰會保存在使用者自己的瀏覽器 localStorage，且 JSONP 會把它放在請求網址參數中。因此只能使用專用隨機金鑰與低敏感度書籤，不可重複使用其他服務密碼。
