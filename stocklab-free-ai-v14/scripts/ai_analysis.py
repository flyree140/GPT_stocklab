"""Free hybrid news analysis.

The pipeline never requires a paid API:
1. Transparent rule model is always available.
2. A small Chinese finance sentiment model can refine direction/confidence.
3. Qwen3-0.6B can explain a limited number of top-relevance articles locally on the
   GitHub Actions runner. If download/inference fails, output automatically falls back.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from common import clamp, normalize_text

LOGGER = logging.getLogger("stocklab.ai")

POSITIVE_TERMS: dict[str, float] = {
    "營收創高": 20,
    "獲利創高": 22,
    "上修": 17,
    "調升": 14,
    "成長": 9,
    "增加": 6,
    "擴產": 8,
    "接單": 12,
    "訂單": 7,
    "合作": 6,
    "得標": 13,
    "併購": 5,
    "股利": 6,
    "買回庫藏股": 10,
    "需求強勁": 14,
    "毛利率提升": 16,
    "優於預期": 18,
    "beat expectations": 18,
    "record revenue": 20,
    "upgrade": 13,
    "growth": 8,
}

NEGATIVE_TERMS: dict[str, float] = {
    "營收衰退": -16,
    "獲利衰退": -18,
    "下修": -17,
    "調降": -14,
    "虧損": -18,
    "減產": -12,
    "裁員": -10,
    "罰款": -11,
    "遭調查": -13,
    "違約": -22,
    "停工": -17,
    "召回": -12,
    "火災": -14,
    "缺料": -10,
    "需求疲弱": -14,
    "毛利率下滑": -16,
    "低於預期": -18,
    "miss expectations": -18,
    "downgrade": -13,
    "decline": -8,
}

CATEGORY_TERMS: list[tuple[str, tuple[str, ...]]] = [
    ("營收與需求", ("營收", "訂單", "需求", "出貨", "銷售", "revenue", "demand")),
    ("獲利與成本", ("獲利", "毛利", "成本", "eps", "profit", "margin")),
    ("資本支出", ("資本支出", "擴產", "新廠", "設備", "capex")),
    ("法規與訴訟", ("法規", "訴訟", "罰款", "調查", "禁令", "regulation", "lawsuit")),
    ("供應鏈", ("供應鏈", "缺料", "庫存", "交期", "supply chain")),
    ("公司治理", ("董事會", "人事", "總經理", "董事長", "治理", "庫藏股")),
    ("併購與合作", ("併購", "收購", "合作", "策略聯盟", "merger", "acquisition")),
    ("股利與籌資", ("股利", "配息", "增資", "發債", "dividend")),
]


def _rule_analysis(news: dict[str, Any]) -> dict[str, Any]:
    text = normalize_text(f"{news.get('title', '')} {news.get('description', '')}")
    raw = 0.0
    evidence: list[str] = []
    for term, weight in POSITIVE_TERMS.items():
        normalized = normalize_text(term)
        if normalized and normalized in text:
            raw += weight
            evidence.append(f"+{term}")
    for term, weight in NEGATIVE_TERMS.items():
        normalized = normalize_text(term)
        if normalized and normalized in text:
            raw += weight
            evidence.append(term)
    if news.get("is_material_info") and abs(raw) < 8:
        raw *= 0.7
    impact = int(round(clamp(raw * 1.55, -100, 100)))
    if impact >= 12:
        sentiment = "positive"
    elif impact <= -12:
        sentiment = "negative"
    else:
        sentiment = "neutral"
    category = "其他事件"
    for label, terms in CATEGORY_TERMS:
        if any(normalize_text(term) in text for term in terms):
            category = label
            break
    magnitude = abs(impact)
    horizon = "1–5 個交易日"
    if category in {"資本支出", "併購與合作", "營收與需求"} and magnitude >= 20:
        horizon = "5–20 個交易日"
    if category in {"法規與訴訟", "供應鏈"} and magnitude >= 35:
        horizon = "1–20 個交易日"
    confidence = clamp(0.50 + min(0.26, len(evidence) * 0.07) + float(news.get("relevance", 0.5)) * 0.12, 0.50, 0.88)
    direction_text = "提高" if impact > 0 else "降低" if impact < 0 else "暫時不改變"
    mechanism = (
        f"此事件較可能透過「{category}」影響市場對未來營收、獲利或風險的預期，"
        f"目前訊號傾向{direction_text}評價；仍需確認金額、持續時間及是否已反映在股價。"
    )
    risks = ["標題資訊可能不完整", "市場可能已提前反映"]
    if magnitude >= 30:
        risks.append("實際影響取決於後續公告與執行")
    return {
        "sentiment": sentiment,
        "impact_score": impact,
        "confidence": round(confidence, 3),
        "horizon": horizon,
        "category": category,
        "mechanism": mechanism,
        "risk_factors": risks,
        "evidence": evidence[:6],
        "analysis_method": "transparent-rule-v2",
    }


@dataclass
class HybridNewsAnalyzer:
    sentiment_model_name: str = "bardsai/finance-sentiment-zh-fast"
    llm_model_name: str = "Qwen/Qwen3-0.6B"
    enable_sentiment: bool = True
    enable_qwen: bool = False

    def __post_init__(self) -> None:
        self._sentiment_pipeline: Any = None
        self._llm_tokenizer: Any = None
        self._llm_model: Any = None
        self._sentiment_failed = False
        self._qwen_failed = False

    def _load_sentiment(self) -> Any | None:
        if not self.enable_sentiment or self._sentiment_failed:
            return None
        if self._sentiment_pipeline is not None:
            return self._sentiment_pipeline
        try:
            from transformers import pipeline  # type: ignore

            token = os.getenv("HF_TOKEN") or None
            self._sentiment_pipeline = pipeline(
                "text-classification",
                model=self.sentiment_model_name,
                tokenizer=self.sentiment_model_name,
                device=-1,
                token=token,
                top_k=None,
            )
            LOGGER.info("Loaded sentiment model %s", self.sentiment_model_name)
            return self._sentiment_pipeline
        except Exception as exc:
            self._sentiment_failed = True
            LOGGER.warning("Sentiment model unavailable; using rules: %s", exc)
            return None

    @staticmethod
    def _label_to_sentiment(label: str) -> str | None:
        text = normalize_text(label)
        if any(term in text for term in ("positive", "pos", "正向", "利多", "label 2", "label2")):
            return "positive"
        if any(term in text for term in ("negative", "neg", "負向", "利空", "label 0", "label0")):
            return "negative"
        if any(term in text for term in ("neutral", "neu", "中性", "label 1", "label1")):
            return "neutral"
        return None

    def _sentiment_refinement(self, text: str) -> dict[str, Any] | None:
        model = self._load_sentiment()
        if model is None:
            return None
        try:
            output = model(text[:900], truncation=True)
            rows = output[0] if output and isinstance(output[0], list) else output
            mapped: dict[str, float] = {}
            for row in rows or []:
                sentiment = self._label_to_sentiment(str(row.get("label", "")))
                if sentiment:
                    mapped[sentiment] = max(mapped.get(sentiment, 0.0), float(row.get("score", 0.0)))
            if not mapped:
                return None
            label = max(mapped, key=mapped.get)
            return {"sentiment": label, "probability": mapped[label], "probabilities": mapped}
        except Exception as exc:
            LOGGER.warning("Sentiment inference failed: %s", exc)
            return None

    def _load_qwen(self) -> tuple[Any, Any] | None:
        if not self.enable_qwen or self._qwen_failed:
            return None
        if self._llm_model is not None and self._llm_tokenizer is not None:
            return self._llm_tokenizer, self._llm_model
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

            token = os.getenv("HF_TOKEN") or None
            self._llm_tokenizer = AutoTokenizer.from_pretrained(self.llm_model_name, token=token)
            self._llm_model = AutoModelForCausalLM.from_pretrained(
                self.llm_model_name,
                torch_dtype="auto",
                device_map="cpu",
                token=token,
                low_cpu_mem_usage=True,
            )
            LOGGER.info("Loaded local LLM %s", self.llm_model_name)
            return self._llm_tokenizer, self._llm_model
        except Exception as exc:
            self._qwen_failed = True
            LOGGER.warning("Qwen unavailable; keeping classifier/rules: %s", exc)
            return None

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        cleaned = text.strip().replace("```json", "").replace("```", "")
        start = cleaned.find("{")
        if start < 0:
            return None
        depth = 0
        for index, char in enumerate(cleaned[start:], start=start):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        value = json.loads(cleaned[start : index + 1])
                        return value if isinstance(value, dict) else None
                    except json.JSONDecodeError:
                        return None
        return None

    def _qwen_analysis(self, stock: dict[str, Any], news: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any] | None:
        loaded = self._load_qwen()
        if loaded is None:
            return None
        tokenizer, model = loaded
        prompt = f"""你是台股新聞事件分析器。只使用提供的新聞，不補充外部事實，也不預測確定漲跌。
公司：{stock.get('name')}（{stock.get('symbol')}）
新聞標題：{news.get('title')}
摘要：{news.get('description', '')}
規則初判：{json.dumps(fallback, ensure_ascii=False)}
請輸出單一 JSON 物件，欄位必須是：
sentiment（positive/neutral/negative）、impact_score（-100 到 100 整數）、confidence（0.50 到 0.95）、horizon（1–5 個交易日/5–20 個交易日/1–20 個交易日）、category、mechanism（60 字內）、risk_factors（最多 3 項字串）。
不要輸出 Markdown，不要加入其他欄位。"""
        messages = [
            {"role": "system", "content": "輸出嚴格 JSON；不提供投資建議。"},
            {"role": "user", "content": prompt},
        ]
        try:
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        try:
            inputs = tokenizer([text], return_tensors="pt")
            output = model.generate(**inputs, max_new_tokens=320, do_sample=False)
            generated = output[0][inputs.input_ids.shape[1] :]
            decoded = tokenizer.decode(generated, skip_special_tokens=True)
            return self._extract_json(decoded)
        except Exception as exc:
            LOGGER.warning("Qwen inference failed: %s", exc)
            return None

    @staticmethod
    def _normalize_llm(value: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
        sentiment = str(value.get("sentiment", fallback["sentiment"])).lower()
        if sentiment not in {"positive", "neutral", "negative"}:
            sentiment = fallback["sentiment"]
        try:
            impact = int(round(float(value.get("impact_score", fallback["impact_score"]))))
        except Exception:
            impact = int(fallback["impact_score"])
        try:
            confidence = float(value.get("confidence", fallback["confidence"]))
        except Exception:
            confidence = float(fallback["confidence"])
        risks = value.get("risk_factors", fallback["risk_factors"])
        if not isinstance(risks, list):
            risks = fallback["risk_factors"]
        return {
            **fallback,
            "sentiment": sentiment,
            "impact_score": int(clamp(impact, -100, 100)),
            "confidence": round(clamp(confidence, 0.50, 0.95), 3),
            "horizon": str(value.get("horizon") or fallback["horizon"])[:40],
            "category": str(value.get("category") or fallback["category"])[:40],
            "mechanism": str(value.get("mechanism") or fallback["mechanism"])[:220],
            "risk_factors": [str(item)[:80] for item in risks[:3]],
            "analysis_method": "qwen3-0.6b-local + hybrid",
        }

    def analyze(self, stock: dict[str, Any], news: dict[str, Any], *, use_qwen: bool = False) -> dict[str, Any]:
        result = _rule_analysis(news)
        text = f"{news.get('title', '')}。{news.get('description', '')}"
        refined = self._sentiment_refinement(text)
        if refined:
            direction = refined["sentiment"]
            probability = float(refined["probability"])
            rule_impact = float(result["impact_score"])
            model_sign = 1 if direction == "positive" else -1 if direction == "negative" else 0
            if model_sign == 0:
                blended = rule_impact * 0.55
            else:
                model_magnitude = 18 + max(0.0, probability - 0.5) * 75
                blended = rule_impact * 0.55 + model_sign * model_magnitude * 0.45
            result["impact_score"] = int(round(clamp(blended, -100, 100)))
            result["sentiment"] = (
                "positive" if result["impact_score"] >= 12 else "negative" if result["impact_score"] <= -12 else "neutral"
            )
            agreement = 1.0 if result["sentiment"] == direction else 0.0
            result["confidence"] = round(
                clamp(float(result["confidence"]) * 0.55 + probability * 0.35 + agreement * 0.10, 0.50, 0.94), 3
            )
            result["analysis_method"] = f"{self.sentiment_model_name} + transparent-rule-v2"
            result["model_probabilities"] = refined.get("probabilities", {})
        if use_qwen:
            llm_result = self._qwen_analysis(stock, news, result)
            if llm_result:
                result = self._normalize_llm(llm_result, result)
        return {**news, **result, "model_version": result["analysis_method"]}
