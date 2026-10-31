# StockLab PaperLab 19.3

這是19.2的相容合併更新，不連券商、不送真實委託。請先閱讀 START_HERE.md。

本版修復跨年期限中斷提案、設定另開試驗、缺乏刪除入口及待成交無原因等問題。新增同一試驗編輯、回收桶、逐日資料診斷、前瞻時間守門、共用模型預算、單次載入批次推論及A/B Colab流程。

原有新聞證據、六面向、K線、虛擬帳務、成本、停止／目標退出、歷史防偷看、雲端私人帳本皆保留。沒有證明獲利，也沒有自動補齊缺失財報／籌碼／官方交易日。

## 離線檢查
```bash
pip install -r requirements.txt
python -m stocklab16.quality
pytest -q
for f in tests/*.mjs; do node "$f"; done
python -m stocklab16.stage
```

## 程式地圖
- assets/paper-engine.mjs：資金、提案、待成交、持股、日結、刪除／還原與時間防護。
- assets/paper.mjs：導覽、設定、管理及日結診斷。
- stocklab193/budget.py：與原版／自有adapter共用持久計數、快取、每輪／每天限制。
- stocklab16/qwen*.py：基底Qwen單程序批次推論，規則分析仍處理全部取得事件。
- stocklab192/runtime.py：自有adapter六面向影子研究，不暗中改交易。
- stocklab193/calendar_update.py：僅嘗試取得有內容的官方年份，不猜假期。
- stocklab193/notebook_flow.py：CPU到GPU的持久化交接與校驗。
- stocklab193/lightweight.py：獨立CPU事件分類器選項，不需Qwen，未自動接入交易評分。

GitHub Pages只發布靜態介面和公開研究JSON，不發布token、Qwen計數快取或私人試驗帳。Colab訓練包另下載，不要把私人資料丟入公開網站。
