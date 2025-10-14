"""
Core logic for the Offshore Transaction Risk Detection System.
"""
import pandas as pd
from datetime import datetime
import logging

from excel_handler import parse_excel, export_to_excel
from fuzzy_matcher import fuzzy_match
from web_research import parallel_web_research
from ai_classifier import classify_with_gpt4
from config import THRESHOLD_KZT, OFFSHORE_JURISDICTIONS, SWIFT_COUNTRY_MAP, FIELD_WEIGHTS_INCOMING, FIELD_WEIGHTS_OUTGOING, FIELD_TRANSLATIONS, SCENARIO_DESCRIPTIONS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_transactions(incoming_file_path, outgoing_file_path):
    """
    Main processing pipeline for offshore transaction detection.
    """
    logging.info("Starting transaction processing.")
    
    # 1. Parse Excel files
    incoming_df = parse_excel(incoming_file_path, 'incoming')
    outgoing_df = parse_excel(outgoing_file_path, 'outgoing')
    
    # 2. Normalize and filter
    incoming_df_filtered = filter_transactions(incoming_df, 'incoming')
    outgoing_df_filtered = filter_transactions(outgoing_df, 'outgoing')
    
    # 3. Detect offshore jurisdictions
    incoming_results = detect_offshore(incoming_df_filtered)
    outgoing_results = detect_offshore(outgoing_df_filtered)
    
    # 4. Export to Excel
    processed_files = export_results(incoming_results, outgoing_results)
    
    logging.info("Transaction processing finished.")
    return processed_files

def filter_transactions(df, direction):
    """
    Filter transactions based on the amount in KZT.
    """
    df['amount_kzt_normalized'] = df['Сумма в тенге'].astype(str).str.replace(' ', '').str.replace(',', '.').astype(float)
    df['direction'] = direction
    df['timestamp'] = datetime.now()
    return df[df['amount_kzt_normalized'] >= THRESHOLD_KZT].copy()

def detect_offshore(df):
    """
    Run offshore detection logic on a dataframe.
    """
    df['Результат'] = df.apply(analyze_transaction, axis=1)
    return df

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
        
        return format_result(final_classification)
    except Exception as e:
        logging.error(f"Error analyzing transaction: {e}")
        return f"Ошибка обработки: {e}"

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

    confidence = calculate_confidence(dict_hits, swift_country_match, matched_fields, match_details)
    
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
    if isinstance(swift_code, str) and len(swift_code) >= 6:
        country_code = swift_code[4:6].upper()
        country_name = SWIFT_COUNTRY_MAP.get(country_code)
        if country_name in OFFSHORE_JURISDICTIONS['en']:
            return country_name
    return None

def calculate_confidence(dict_hits, swift_country_match, matched_fields, match_details):
    """
    Calculate confidence score based on signals.
    """
    confidence = 0.0
    if len(dict_hits) > 0: confidence += 0.4
    if swift_country_match: confidence += 0.3
    if 'Страна резидентства' in matched_fields: confidence += 0.2
    if any(f in matched_fields for f in ['Банк плательщика', 'Банк получателя']): confidence += 0.1
    if any(f in matched_fields for f in ['Плательщик', 'Получатель']): confidence += 0.15
    if match_details:
        avg_similarity = sum(d['similarity'] for d in match_details) / len(match_details)
        confidence += avg_similarity * 0.1
    if len(dict_hits) > 1: confidence += 0.1
    if len(matched_fields) > 2: confidence += 0.1
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

def format_result(classification_data):
    """
    Format the final result string for the Excel output.
    """
    classification = classification_data.get('classification', 'ОФШОР: НЕТ')
    scenario = classification_data.get('scenario')
    confidence = classification_data.get('confidence', 0.0)
    explanation_ru = classification_data.get('explanation_ru', 'Нет данных.')
    matched_fields = classification_data.get('matched_fields', [])
    sources = classification_data.get('sources', [])

    translated_fields = [FIELD_TRANSLATIONS.get(f, f) for f in matched_fields]

    result_parts = [
        f"Итог: {classification}",
        f"Сценарий {scenario}: {SCENARIO_DESCRIPTIONS[scenario]}" if scenario and scenario in SCENARIO_DESCRIPTIONS else None,
        f"Уверенность: {int(confidence * 100)}%",
        f"Объяснение: {explanation_ru}",
        f"Совпадения в полях: {', '.join(translated_fields)}" if translated_fields else None,
        f"Источники: {'; '.join(sources)}" if sources else None
    ]
    return ' | '.join([p for p in result_parts if p])

def export_results(incoming_df, outgoing_df):
    """
    Export dataframes to Excel files.
    """
    now = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    
    incoming_filename = f"incoming_transactions_processed_{now}.xlsx"
    outgoing_filename = f"outgoing_transactions_processed_{now}.xlsx"
    
    export_to_excel(incoming_df, incoming_filename, "Входящие операции")
    export_to_excel(outgoing_df, outgoing_filename, "Исходящие операции")
    
    return [incoming_filename, outgoing_filename]
