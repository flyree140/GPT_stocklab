# 歷史與試買

每次成功 Daily build 都會更新：

- `data/latest.json`
- `data/snapshots/YYYY-MM-DD.json`
- `data/manifest.json`

網站只列出 manifest 內真的存在的日期。

試買流程：

- T 日：只保存訊號。
- 使用者按「揭曉」後才載入 `data/market/SYMBOL.json`。
- T+1 第一個有成交量的開盤價進場。
- 支援停損、停利、手續費、交易稅、滑價與最低手續費模擬。
- 同日同時碰停損和停利，採保守停損優先。
- 遇到 corporate action 標記時停止簡化回測。
