# StockLab PaperLab 19.3.2

相容19.3的合併升級：真實教材、自己的LoRA接線、核心＋輪替股票池、所有分析的開發者驗證、外資流向支撐代理。原個人試驗、Google雲端設定、歷史資料均保留。不連券商、不送真實委託。

請先閱讀 START_HERE.md；流程圖與操作教學在 pipeline1932.html。新入口 developer1932.html。正式與測試邊界詳見 BUILD_REPORT.md。

## 新功能與限制
- 每檔獨立虛擬預算，一鍵保存全部決策；只對符合規則者建試單，原避開／觀望仍保留。
- 被動1/5/10/20日探針追蹤全部股票，不受個人資金限制；不是原始建議的實際成交，也不是新聞因果或模型預測準確率。
- 自己的adapter仍以影子輸出保存，不自動取代原始研究評分；需同版本基底。合成smoke權重禁止正式部署。
- 官方法人每日增量蒐集，缺日期／欄位／資料不畫線；代理不是外資真實持倉成本。
- 核心＋輪替仍有每日深度額度，不宣稱每天全市場所有新聞／財報皆完整。
- 取得600筆真實待標註標題不等於已有600筆標準答案；私人訓練包不可上傳公開Repository。

## 本機驗證
```sh
pip install -r requirements.txt
python -m stocklab16.quality
pytest -q
for f in tests/*.mjs; do node "$f"; done
python -m stocklab16.stage
```

## 安全覆蓋
只將本包全部內容合併到根目錄，不要先刪除data/或config/。cloud-config.json沒有在包內。既有本機帳本與新的開發者批次分開；請自行定期備份並同步私人活頁簿。
