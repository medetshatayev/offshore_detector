"""
Core logic for the Offshore Transaction Risk Detection System.
"""
import pandas as pd
from datetime import datetime
import logging

from excel_handler import parse_excel, export_to_excel
from analyzer import analyze_transaction
from config import THRESHOLD_KZT, FIELD_TRANSLATIONS, SCENARIO_DESCRIPTIONS

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
    Fixed: Proper handling of various number formats.
    """
    def parse_amount(value):
        """Parse amount handling different locale formats."""
        if pd.isna(value):
            return 0.0
        s = str(value).strip().replace(' ', '').replace('\xa0', '')  # Remove spaces and non-breaking spaces
        # If there are multiple dots/commas, assume thousands separator
        if s.count(',') > 1 or s.count('.') > 1:
            s = s.replace(',', '').replace('.', '')
        elif ',' in s and '.' in s:
            # Determine which is decimal separator (appears last)
            if s.rindex(',') > s.rindex('.'):
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        elif ',' in s:
            # If only comma, check if it looks like decimal separator
            parts = s.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                s = s.replace(',', '.')
            else:
                s = s.replace(',', '')
        try:
            return float(s)
        except (ValueError, AttributeError):
            return 0.0
    
    df['amount_kzt_normalized'] = df['Сумма в тенге'].apply(parse_amount)
    df['direction'] = direction
    df['timestamp'] = datetime.now()
    return df[df['amount_kzt_normalized'] >= THRESHOLD_KZT].copy()

def detect_offshore(df):
    """
    Run offshore detection logic on a dataframe.
    PERFORMANCE NOTE: df.apply() processes rows sequentially. For large datasets,
    consider using parallel processing with multiprocessing.Pool or concurrent.futures.
    """
    df_copy = df.copy()
    logging.info(f"Processing {len(df_copy)} transactions...")
    df_copy['Результат'] = df_copy.apply(lambda row: format_result(analyze_transaction(row)), axis=1)
    return df_copy

def format_result(classification_data):
    """
    Format the final result string for the Excel output.
    Fixed: Proper null checking for scenario.
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
        f"Сценарий {scenario}: {SCENARIO_DESCRIPTIONS.get(scenario, 'Неизвестно')}" if scenario is not None else None,
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
