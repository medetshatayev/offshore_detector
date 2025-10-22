"""
OpenAI GPT integration for transaction classification.
"""
from openai import OpenAI
import os
import json
import logging
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

def classify_with_gpt4(transaction_data, preliminary_analysis):
    """
    Classify a transaction using OpenAI's GPT model.
    """
    if not OPENAI_API_KEY:
        logging.warning("OPENAI_API_KEY not found. Using fallback classification.")
        return fallback_classification(preliminary_analysis)

    system_prompt = """
You are an expert financial compliance analyst specializing in offshore risk detection for Kazakhstan regulatory requirements. Analyze the provided transaction data and supporting evidence to classify offshore risk according to these scenarios:

Scenario 1: ВХОДЯЩИЕ - Платеж получен от плательщика, зарегистрированного/проживающего/находящегося в офшорной зоне или оплачивающего со счета в банке офшорной зоны

Scenario 2: ИСХОДЯЩИЕ - Платеж отправлен получателю, зарегистрированному/проживающему/находящемуся в офшорной зоне или получающему на счет в банке офшорной зоны

Scenario 3: Операции клиента с деньгами/имуществом лиц, зарегистрированных/проживающих/находящихся в офшорной зоне или владеющих счетами в офшорных банках

You must respond with ONLY a valid JSON object matching this exact schema:

{
  "classification": "ОФШОР: ДА" | "ОФШОР: ПОДОЗРЕНИЕ" | "ОФШОР: НЕТ",
  "scenario": 1 | 2 | 3 | null,
  "confidence": 0.0-1.0,
  "matched_fields": ["field1", "field2"],
  "signals": {
    "swiftCountry": "country_name",
    "geoCountry": "country_name",
    "dictHits": ["jurisdiction1"],
    "keywords": ["keyword1"]
  },
  "sources": ["https://url1", "https://url2"],
  "explanation_ru": "краткое объяснение на русском языке"
}
"""

    direction = transaction_data['direction']
    counterparty = transaction_data.get('Плательщик') or transaction_data.get('Получатель')
    bank = transaction_data.get('Банк плательщика') or transaction_data.get('Банк получателя')
    swift_code = transaction_data.get('SWIFT Банка плательщика') or transaction_data.get('SWIFT Банка получателя')
    amount = transaction_data['amount_kzt_normalized']
    residence_country = transaction_data.get('Страна резидентства')
    city = transaction_data.get('Город')

    user_prompt = f"""Проанализируйте данную транзакцию:

Направление: {direction}
Контрагент: {counterparty}
Банк: {bank}
SWIFT: {swift_code}
Сумма (KZT): {amount}
Страна резидентства: {residence_country}
Город: {city}

Предварительный анализ:
{json.dumps(preliminary_analysis, ensure_ascii=False, indent=2)}

Предоставьте окончательную классификацию только в формате JSON."""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=4096
        )
        
        response_content = response.choices[0].message.content
        
        # Clean and parse JSON
        json_str = response_content.strip().replace('```json', '').replace('```', '').strip()
        return json.loads(json_str)

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
