"""
Core analysis functions for the Offshore Transaction Risk Detection System.
"""
import pandas as pd
import logging

from fuzzy_matcher import fuzzy_match
from web_research import parallel_web_research
from ai_classifier import classify_with_gpt4
from config import OFFSHORE_JURISDICTIONS, SWIFT_COUNTRY_MAP, FIELD_WEIGHTS_INCOMING, FIELD_WEIGHTS_OUTGOING

def analyze_transaction(row):
    """
    Analyze a single transaction row.
    """
    try:
        preliminary_analysis = run_preliminary_analysis(row)
        
        if preliminary_analysis['confidence'] > 0.2:
            web_results = parallel_web_research(
                row.get('Плательщик') or row.get('Получатель'),
                row.get('Банк плательщика') or row.get('Банк получателя')
            )
            preliminary_analysis['web_results'] = web_results
        
        final_classification = classify_with_gpt4(row, preliminary_analysis)
        
        return final_classification
    except Exception as e:
        logging.error(f"Error analyzing transaction: {e}")
        return {
            "classification": "ОШИБКА",
            "scenario": None,
            "confidence": 0.0,
            "matched_fields": [],
            "signals": {},
            "sources": [],
            "explanation_ru": f"Ошибка обработки: {str(e)}"
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
    Extract country from SWIFT code and check if it's offshore.
    """
    if not isinstance(swift_code, str):
        return None
    
    # SWIFT/BIC codes are 8 or 11 characters
    swift_clean = swift_code.strip().upper()
    if len(swift_clean) not in (8, 11):
        return None
    
    # Country code is at positions 4:6
    country_code = swift_clean[4:6]
    country_name = SWIFT_COUNTRY_MAP.get(country_code)
    if country_name and country_name in OFFSHORE_JURISDICTIONS['en']:
        return country_name
    return None

def calculate_confidence(dict_hits, swift_country_match, matched_fields, match_details, field_weights):
    """
    Calculate confidence score based on signals.
    """
    confidence = 0.0
    
    # Base confidence from dictionary and SWIFT hits (max 0.5 combined)
    if dict_hits:
        confidence += 0.3
    if swift_country_match:
        confidence += 0.2
        
    # Add confidence based on matched fields and their weights (scaled down to max 0.3)
    field_score = 0.0
    for field in matched_fields:
        if field in field_weights:
            field_score += field_weights[field]
    confidence += min(field_score, 1.0) * 0.3  # Scale field weights to max 0.3

    # Bonus for multiple signals (max 0.1 combined)
    if len(dict_hits) > 1:
        confidence += 0.05
    if len(matched_fields) > 2:
        confidence += 0.05
        
    # Factor in fuzzy match similarity (max 0.1)
    if match_details:
        avg_similarity = sum(d['similarity'] for d in match_details) / len(match_details)
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
