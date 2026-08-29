# 歷史驗證與防止偷看未來

## 核心原則

在切點 `T` 做預測時，任何輸入資料都必須滿足：

```text
available_at <= T
```

不是只看新聞文章內提到的日期，而是看市場何時真正可取得這筆資訊。

## Snapshot 與 Result 分離

```text
data/snapshots/2025-08-15.json   # 輸入、特徵、分數、預測
data/results/2025-08-15.json     # 明確 reveal 後才產生的實際結果
```

Snapshot 禁止包含：

- `actual_return`
- `future_price`
- `outcome`
- `direction_hit`
- `brier_score`
- 任何等價的事後答案欄位

## 前端不自動揭曉

歷史驗證頁初次只載入 snapshot。即使 Repository 已經有 result 檔，前端也要使用者完整輸入 `REVEAL` 才發出 request。

## 回溯建立的誠實標示

現在重建 2025-08-15，仍然是「事後回溯重播」，不是 2025-08-15 當天事先登記的預測。系統會保存：

- `retrospective: true`
- `generated_at`：實際建立日期
- `as_of`：模擬的資料切點

真正嚴格的前瞻驗證，應從現在開始每天自動提交不可變 snapshot，日後再 reveal。

## 現行免費資料的限制

TWSE 某些 OpenAPI 是「目前最新快照」，不適合直接用於一年前的回測。因此 `historical=True` 時：

- 歷史價格：可取。
- T86 指定日期籌碼：可取。
- GDELT 歷史新聞：可取並按切點過濾。
- 今日最新估值/月營收：不倒填，先留空。
- 若未來補入真正 archive，才可提高歷史基本面完整度。

這個選擇會讓分數看起來比較不完整，但比偷偷使用未來資料可信。

## 指令

只產生 snapshot：

```bash
python scripts/backtest.py --as-of 2025-08-15 --skip-qwen
```

檢查：

```bash
python scripts/validate_no_leak.py data/snapshots/2025-08-15.json
```

明確揭曉：

```bash
python scripts/backtest.py --as-of 2025-08-15 --reveal --skip-qwen
```

## 評估指標

Result 可計算：

- 方向命中率
- Brier Score
- 1/5/20 日報酬
- 未來可加入相對 0050 的異常報酬
- 依新聞分、來源、產業與信心分桶的命中率
- 交易成本後報酬與最大回撤

單一日期或單一股票不足以證明模型可信，應使用多日期 walk-forward 驗證。
