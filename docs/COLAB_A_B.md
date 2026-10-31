# StockLab 19.3｜A CPU → B GPU，主線不跳格

## 我到底上傳什麼？

只在Colab開啟 .ipynb。A、B都已內嵌程式，會自己建立 stocklab193-program 資料夾，絕不要求上傳StockLab192。第一次smoke也不需要新聞資料檔。

正式教材是「你核對過的 reviewed.jsonl」，不是程式資料夾，不是Qwen權重，不是原網站ZIP。原網站ZIP只能透過C轉成待標註清單，不能直接當答案。

## A：先用CPU，四格全跑

A1：MODE=smoke、JOB_NAME=first-run。smoke是24則手寫合成案例；reviewed才使用自己的核准教材。
A2：自動解出程式，完成Drive授權。資料固定在 我的雲端硬碟/StockLab193。
A3：核對結構、時間、事件群、原文引用與使用權，切成train/validation/test，寫 READY.json。
A4：執行六面向CPU示範並顯示「A完成」。不要在A切GPU；關閉A，開B。

A完成後檔案為：
```
我的雲端硬碟/StockLab193/
  LAST_READY.json
  jobs/first-run/READY.json
  jobs/first-run/data/train.jsonl
  jobs/first-run/data/validation.jsonl
  jobs/first-run/data/test.jsonl
```

A的切分與程式hash永久保存。B自己讀取，不靠A記憶體的DATA變數，因此不再有第3格沒跑就第5格NameError的動線。

## B：選GPU，勾一次同意，四格全跑

B1：Colab選GPU，勾 CONSENT_GPU；JOB_NAME留空就選最後一次成功A。完成Drive授權。無GPU會清楚停止，不自動付費。
B2：安裝固定依賴並訓練。資料未改則可自動續訓；有已完成且校驗相同的adapter則不重訓。LoRA預設；QLoRA選項保留。
B3：同資料比較原版與adapter。預設validation，最多8筆小批比較；最後測試集需你明確選test。已有同模型同資料結果不重跑。
B4：保存並下載adapterZIP，不帶私人新聞。完成後停止／刪除GPU執行階段。

不要先在Colab開GPU再慢慢整理新聞。不要因為小樣本F1上升就發布投資績效。

## 合成資料有準確性嗎？

24則是程式作者手寫的可控教學情境，不是真實市場樣本，不具有已估計的金融準確率。用途是檢查tokenization、LoRA、checkpoint和JSON抽取流程。即使24筆全部答對，也不能證明會分析真實新聞或預測股價。

reviewed模式拒絕合成資料；網站部署驗證器拒絕 synthetic_smoke_only 權重。正式研究應準備人工核對、具來源權利、可查發布時間、事件群去重的中英文新聞／公告，使用時間切分、原版對照、人工語意抽查及往後新事件的影子測試。

## 沒有刪掉的功能

LoRA/QLoRA、僅答案token訓練、原文證據檢查、時間切分、事件跨集合排除、長度檢查、GPU步數/token/時間限制、checkpoint續訓、原版/adapter比較、保留最終測試、adapter雜湊與基底修訂核對皆保留。

正式起步仍最多1000筆train、200更新步硬上限、不超過一輪、2048 tokens、30分鐘軟預算；超過資料上限直接停止讓你選資料，不偷偷刪樣本。smoke最多6更新步與10分鐘軟預算。這是程式預算，不是Colab免費額度保證。

## C：只有有需要才開的CPU工具箱

不需GPU，兩格由上到下，選一種任務：
- archive：原網站ZIP轉待人工標註的新聞清單，下載annotation.html。
- social：你核對權利的Bluesky作者樣本，最多30篇，非全平台情緒。
- light_classifier：字元TF-IDF＋LogisticRegression獨立模型，JSON權重，不需要Qwen基底。只作事件分類，不產生完整證據報告或股數。
- return_baseline：六面向CPU Ridge報酬基準，需要獨立成熟結果標籤與時間切點，沒有標籤不假造。
- publish：把reviewed adapter放私人HF庫，輸出GitHub設定，不上傳私人教材。

## 模型與網站串接

LoRA是Qwen的增量參數，不是獨立小模型。推論仍要同版Qwen基底+adapter，但不需要付費Qwen API。

GitHub Variables：STOCKLAB_192_ENABLED=1、STOCKLAB_ADAPTER_REPO、STOCKLAB_ADAPTER_REVISION（40位commit SHA）；只讀Token放HF_TOKEN Secret。不要放前端、試算表或公開Notebook輸出。

19.3先把新權重寫到六面向影子頁，不改歷史／持股／已確認的試單。原版／自有權重共用12/6每日／每輪預算。

要完全不依賴Qwen，C的獨立CPU分類器是一條路，但它只有分類能力。llama.cpp量化是另一條優化路徑，本包未實作GGUF匯出或量化後精度驗證，不宣稱它已接入網站。

## 免費與驗收限制

沒有GPU保證供應。沒有自動付費、多帳號或保活。不把你的期望收益當模型標籤，不把社群讚數視為買點。
本次驗證CPU教材切分、A→B持久化、語法、GPU同意／無CUDA守門；沒有實際跑GPU訓練、下載Qwen或連接你的私人HF/Drive。
