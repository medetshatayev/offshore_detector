"""
Core analysis functions for the Offshore Transaction Risk Detection System.
Adds structured per-row logging with timings and swift-derived signals.
"""
import pandas as pd
import logging
import time
import json

from fuzzy_matcher import fuzzy_match
from web_research import parallel_web_research
from ai_classifier import classify_with_gpt4
from config import OFFSHORE_JURISDICTIONS, SWIFT_COUNTRY_MAP, FIELD_WEIGHTS_INCOMING, FIELD_WEIGHTS_OUTGOING

def analyze_transaction(row):
    """
    Analyze a single transaction row.
    Optimized to cache frequently accessed values and improve readability.
    """
    try:
        t0 = time.time()
        
        # Cache frequently accessed row values to avoid repeated lookups
        direction = row.get('direction')
        swift_code = row.get('SWIFT Банка плательщика') or row.get('SWIFT Банка получателя')
        counterparty = row.get('Плательщик') or row.get('Получатель')
        bank = row.get('Банк плательщика') or row.get('Банк получателя')
        
        # Run preliminary analysis
        preliminary_analysis = run_preliminary_analysis(row)
        
        # Perform geocoding
        tg0 = time.time()
        web_results = parallel_web_research(counterparty, bank, swift_code)
        geocode_ms = int((time.time() - tg0) * 1000)
        preliminary_analysis['web_results'] = web_results

        # Get final classification from GPT-4
        to0 = time.time()
        final_classification = classify_with_gpt4(row, preliminary_analysis)
        openai_ms = int((time.time() - to0) * 1000)
        total_ms = int((time.time() - t0) * 1000)

        # Log structured summary
        _log_transaction_summary(
            row, direction, preliminary_analysis, final_classification,
            geocode_ms, openai_ms, total_ms
        )

        return final_classification
        
    except Exception as e:
        logging.error(f"Error analyzing transaction: {e}", exc_info=True)
        return _create_error_classification(e)


def _log_transaction_summary(row, direction, preliminary_analysis, final_classification,
                             geocode_ms, openai_ms, total_ms):
    """
    Log a structured summary of the transaction analysis.
    Separated for better readability and testability.
    Note: Does not log PII (counterparty/bank names), only metadata and classification results.
    """
    try:
        row_idx = getattr(row, 'name', 'unknown')
        swift_country = preliminary_analysis.get('swift_country_match')
        payload = {
            "row": row_idx,
            "direction": direction,
            "swift_country": swift_country,  # Country name only, not PII
            "swift_offshore": bool(swift_country),
            "prelim_conf": round(preliminary_analysis.get('confidence', 0.0), 3),
            "final_class": final_classification.get('classification'),
            "final_scen": final_classification.get('scenario'),
            "final_conf": final_classification.get('confidence'),
            "sources_count": len(final_classification.get('sources') or []),
            "ms": {"geocode": geocode_ms, "openai": openai_ms, "total": total_ms}
        }
        logging.info("Row summary: %s", json.dumps(payload, ensure_ascii=False))
    except Exception as e:
        logging.debug(f"Failed to log transaction summary: {e}")


def _create_error_classification(error):
    """
    Create a standardized error classification response.
    """
    return {
        "classification": "ОШИБКА",
        "scenario": None,
        "confidence": 0.0,
        "matched_fields": [],
        "signals": {},
        "sources": [],
        "explanation_ru": f"Ошибка обработки: {str(error)}"
    }

def run_preliminary_analysis(row):
    """
    Perform dictionary and SWIFT code analysis.
    """
    dict_hits = []
    matched_fields = set()
    match_details = []

    field_weights = FIELD_WEIGHTS_INCOMING if row['direction'] == 'incoming' else FIELD_WEIGHTS_OUTGOING
    
    for field, weight in field_weights.items():
        if field in row and pd.notna(row[field]):
            text_to_check = str(row[field])
            for lang, jurisdictions in OFFSHORE_JURISDICTIONS.items():
                matches = fuzzy_match(text_to_check, jurisdictions)
                if matches:
                    dict_hits.extend([m['match'] for m in matches])
                    matched_fields.add(field)
                    match_details.extend(matches)

    swift_code = row.get('SWIFT Банка плательщика') or row.get('SWIFT Банка получателя')
    swift_country_match = extract_country_from_swift(swift_code)

    confidence = calculate_confidence(dict_hits, swift_country_match, matched_fields, match_details, field_weights)
    
    scenario = classify_scenario(row['direction'], dict_hits, swift_country_match)

    return {
        'dict_hits': list(set(dict_hits)),
        'swift_country_match': swift_country_match,
        'confidence': confidence,
        'scenario': scenario,
        'matched_fields': list(matched_fields),
        'match_details': match_details
    }

def extract_country_from_swift(swift_code):
    """
    Extract country from SWIFT/BIC code and check if it's an offshore jurisdiction.
    
    SWIFT codes are 8 or 11 characters: AAAABBCCXXX
    - AAAA: Bank code
    - BB: Country code (positions 4-6)
    - CC: Location code
    - XXX: Branch code (optional)
    
    Args:
        swift_code: SWIFT/BIC code string
    
    Returns:
        Country name if offshore jurisdiction, None otherwise
    """
    if not isinstance(swift_code, str) or not swift_code:
        return None
    
    # SWIFT/BIC codes are 8 or 11 characters
    swift_clean = swift_code.strip().upper()
    if len(swift_clean) not in (8, 11):
        logging.debug(f"Invalid SWIFT code length: {len(swift_clean)}")
        return None
    
    # Country code is at positions 4:6
    country_code = swift_clean[4:6]
    
    # Validate country code is alphabetic
    if not country_code.isalpha():
        logging.debug(f"Invalid country code in SWIFT: {country_code}")
        return None
    
    # Look up country name and check if offshore
    country_name = SWIFT_COUNTRY_MAP.get(country_code)
    if country_name and country_name in OFFSHORE_JURISDICTIONS['en']:
        return country_name
    
    return None

def calculate_confidence(dict_hits, swift_country_match, matched_fields, match_details, field_weights):
    """
    Calculate confidence score based on various signals.
    
    Confidence is built from multiple sources:
    - Dictionary hits (max 0.3)
    - SWIFT country match (max 0.2)
    - Field weights (max 0.3)
    - Multiple signal bonus (max 0.1)
    - Fuzzy match quality (max 0.1)
    
    Args:
        dict_hits: List of offshore jurisdiction matches
        swift_country_match: Country extracted from SWIFT code if offshore
        matched_fields: Fields that had matches
        match_details: Details of fuzzy matches with similarity scores
        field_weights: Weight mapping for different fields
    
    Returns:
        Confidence score between 0.0 and 1.0
    """
    confidence = 0.0
    
    # Base confidence from dictionary and SWIFT hits (max 0.5 combined)
    if dict_hits:
        confidence += 0.3
    if swift_country_match:
        confidence += 0.2
        
    # Add confidence based on matched fields and their weights (max 0.3)
    field_score = sum(field_weights.get(field, 0.0) for field in matched_fields)
    confidence += min(field_score, 1.0) * 0.3

    # Bonus for multiple signals (max 0.1 combined)
    if len(dict_hits) > 1:
        confidence += 0.05
    if len(matched_fields) > 2:
        confidence += 0.05
        
    # Factor in fuzzy match quality (max 0.1)
    if match_details:
        avg_similarity = sum(d.get('similarity', 0.0) for d in match_details) / len(match_details)
        confidence += avg_similarity * 0.1

    return min(confidence, 1.0)

def classify_scenario(direction, dict_hits, swift_country_match):
    """
    Classify transaction scenario.
    """
    if direction == 'incoming' and (dict_hits or swift_country_match):
        return 1
    elif direction == 'outgoing' and (dict_hits or swift_country_match):
        return 2
    elif dict_hits or swift_country_match:
        return 3
    return None
