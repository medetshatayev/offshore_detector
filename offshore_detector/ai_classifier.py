"""
OpenAI GPT integration for transaction classification.
Updated to use the Responses API with web_search tool and structured output.
"""
from openai import OpenAI
import json
import logging
from .config import OPENAI_API_KEY, OFFSHORE_JURISDICTIONS, SCENARIO_DESCRIPTIONS

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

def _extract_output_text(resp):
    if hasattr(resp, "output_text") and resp.output_text:
        return resp.output_text
    try:
        parts = []
        for item in getattr(resp, "output", []):
            for c in getattr(item, "content", []):
                if getattr(c, "type", "") == "output_text" and getattr(c, "text", None):
                    parts.append(c.text)
        return "\n".join(parts) if parts else None
    except Exception:
        return None

def classify_with_gpt4(transaction_data, preliminary_analysis):
    """
    Classify a transaction using OpenAI Responses API with optional web search.
    Passes geocoding results, offshore jurisdictions, and scenario descriptions.
    """
    if not OPENAI_API_KEY or client is None:
        logging.warning("OPENAI_API_KEY not found. Using fallback classification.")
        return fallback_classification(preliminary_analysis)

    system_instructions = (
        "You are an expert financial compliance analyst for a Kazakhstani bank. "
        "Analyze the provided transaction and determine offshore risk. "
        "You may use the web_search tool to find up-to-date public information about the counterparty or bank. "
        "When you use web_search, include the most relevant source URLs in the 'sources' field. "
        "Respond ONLY with a JSON object matching the required schema."
    )

    direction = transaction_data.get('direction')
    counterparty = transaction_data.get('Плательщик') or transaction_data.get('Получатель')
    bank = transaction_data.get('Банк плательщика') or transaction_data.get('Банк получателя')
    swift_code = transaction_data.get('SWIFT Банка плательщика') or transaction_data.get('SWIFT Банка получателя')
    amount = transaction_data.get('amount_kzt_normalized')
    residence_country = transaction_data.get('Страна резидентства')
    city = transaction_data.get('Город')

    geocoding = None
    try:
        geocoding = preliminary_analysis.get('web_results', {}).get('geocoding')
    except Exception:
        geocoding = None

    # Heuristic to encourage web search usage
    must_search = False
    reasons = []
    prelim_conf = float(preliminary_analysis.get('confidence') or 0.0)
    if 0.3 <= prelim_conf <= 0.9:
        must_search = True
        reasons.append("mid_confidence")
    if (preliminary_analysis.get('dict_hits') or []):
        must_search = True
        reasons.append("dict_hits_present")
    if not geocoding:
        must_search = True
        reasons.append("geocoding_missing")

    payload = {
        "transaction": {
            "direction": direction,
            "counterparty": counterparty,
            "bank": bank,
            "swift": swift_code,
            "residence_country": residence_country,
            "city": city,
        },
        "preliminary_analysis": preliminary_analysis,
        "geocoding": geocoding,
        "offshore_jurisdictions": OFFSHORE_JURISDICTIONS,
        "scenario_descriptions": SCENARIO_DESCRIPTIONS,
        "search_guidance": {"must_search": must_search, "reasons": reasons},
        "response_schema": {
            "classification": ["ОФШОР: ДА", "ОФШОР: ПОДОЗРЕНИЕ", "ОФШОР: НЕТ"],
            "scenario": [1, 2, 3, None],
            "confidence": "float 0-1",
            "matched_fields": "list[str]",
            "signals": {
                "swiftCountry": "str | null",
                "geoCountry": "str | null",
                "dictHits": "list[str]",
                "keywords": "list[str] | optional"
            },
            "sources": "list[str]",
            "explanation_ru": "str"
        }
    }

    user_text = (
        "Проанализируйте транзакцию и выполните классификацию офшорного риска. "
        "Если нужно уточнить сведения о контрагенте/банке, используйте web_search. "
        "Верните только валидный JSON согласно схеме.\n\n" + json.dumps(payload, ensure_ascii=False)
    )

    # Build a compact logging context
    try:
        def oneline(s):
            return (s or "").replace("\n", " ").replace("\r", " ")
        summary_ctx = {
            "direction": direction,
            "counterparty": oneline(counterparty)[:120],
            "bank": oneline(bank)[:120],
            "swift": swift_code,
            "prelim": {
                "confidence": preliminary_analysis.get('confidence'),
                "scenario": preliminary_analysis.get('scenario'),
                "dict_hits": (preliminary_analysis.get('dict_hits') or [])[:5],
                "matched_fields": preliminary_analysis.get('matched_fields')
            },
            "geocoding_display": ((geocoding or [None])[0] or {}).get('display_name') if isinstance(geocoding, list) else None
        }
    except Exception:
        summary_ctx = {"direction": direction, "swift": swift_code}

    try:
        # Log structured summary of what is being sent (not the full payload)
        logging.info("OpenAI request context: %s", json.dumps(summary_ctx, ensure_ascii=False))
        req = {
            "model": "gpt-4.1",
            "instructions": system_instructions.strip(),
            "input": [{"role": "user", "content": user_text}],
            "tools": [{"type": "web_search"}],
            "tool_choice": "auto",
            'metadata': {"user_location": f"Country: KZ, Timezone: Asia/Almaty"}
        }
        resp = client.responses.create(**req)

        text = _extract_output_text(resp)
        if not text:
            raise ValueError("Empty response from model")

        json_str = text.strip().replace('```json', '').replace('```', '').strip()
        result = json.loads(json_str)
        # Confidence hygiene: if no sources and no SWIFT offshore signal, cap confidence
        try:
            has_sources = bool(result.get("sources"))
            swift_offshore = bool(preliminary_analysis.get('swift_country_match'))
            if not has_sources and not swift_offshore:
                result["confidence"] = min(float(result.get("confidence") or 0.0), 0.7)
        except Exception:
            pass
        # Log a concise response summary
        try:
            resp_summary = {
                "classification": result.get("classification"),
                "scenario": result.get("scenario"),
                "confidence": result.get("confidence"),
                "matched_fields": result.get("matched_fields"),
                "sources_count": len(result.get("sources") or []),
            }
            logging.info("OpenAI response summary: %s", json.dumps(resp_summary, ensure_ascii=False))
        except Exception:
            logging.info("OpenAI response received (summary unavailable)")
        return result

    except Exception as e:
        logging.error(f"Error in GPT classification: {e}")
        return fallback_classification(preliminary_analysis)

def fallback_classification(preliminary_analysis):
    """
    Fallback classification logic if GPT fails.
    """
    confidence = preliminary_analysis.get('confidence', 0.0)
    if confidence > 0.7:
        classification = "ОФШОР: ДА"
    elif confidence > 0.3:
        classification = "ОФШОР: ПОДОЗРЕНИЕ"
    else:
        classification = "ОФШОР: НЕТ"
    
    return {
        "classification": classification,
        "scenario": preliminary_analysis.get('scenario'),
        "confidence": confidence,
        "matched_fields": preliminary_analysis.get('matched_fields', []),
        "signals": {
            "swiftCountry": preliminary_analysis.get('swift_country_match'),
            "dictHits": preliminary_analysis.get('dict_hits', [])
        },
        "sources": [],
        "explanation_ru": "Классификация на основе предварительного анализа (GPT недоступен)."
    }
