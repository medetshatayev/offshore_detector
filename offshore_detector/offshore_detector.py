"""
Core logic for the Offshore Transaction Risk Detection System.
"""
import pandas as pd
from datetime import datetime
import logging

from excel_handler import parse_excel, export_to_excel
from analyzer import analyze_transaction
from config import THRESHOLD_KZT

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
    Normalizes amount field and filters by threshold.
    
    Args:
        df: DataFrame with transaction data
        direction: 'incoming' or 'outgoing'
    
    Returns:
        Filtered DataFrame with normalized amounts
    """
    # Parse and normalize amounts
    df['amount_kzt_normalized'] = df['Сумма в тенге'].apply(_parse_amount)
    df['direction'] = direction
    df['timestamp'] = datetime.now()
    
    # Filter by threshold
    filtered_df = df[df['amount_kzt_normalized'] >= THRESHOLD_KZT].copy()
    
    logging.info(
        f"Filtered {direction} transactions: {len(filtered_df)} of {len(df)} "
        f"meet threshold of {THRESHOLD_KZT:,.0f} KZT"
    )
    
    return filtered_df


def _parse_amount(value):
    """
    Parse amount handling different locale formats.
    Supports various number formats with commas and periods.
    
    Args:
        value: Amount value (can be float, int, or string)
    
    Returns:
        Parsed float value, or 0.0 if parsing fails
    """
    if pd.isna(value):
        return 0.0
    
    # Handle numeric types directly
    if isinstance(value, (int, float)):
        return float(value)
    
    # Clean string representation
    s = str(value).strip()
    s = s.replace(' ', '').replace('\xa0', '')  # Remove spaces
    
    if not s:
        return 0.0
    
    try:
        # Handle multiple separators (likely thousands separators)
        if s.count(',') > 1 or s.count('.') > 1:
            # Remove all separators and treat as integer
            s = s.replace(',', '').replace('.', '')
            return float(s)
        
        # Both comma and period present
        if ',' in s and '.' in s:
            # The last one is the decimal separator
            if s.rindex(',') > s.rindex('.'):
                # Comma is decimal separator (European format)
                s = s.replace('.', '').replace(',', '.')
            else:
                # Period is decimal separator (US format)
                s = s.replace(',', '')
        
        # Only comma present
        elif ',' in s:
            parts = s.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                # Likely decimal separator
                s = s.replace(',', '.')
            else:
                # Likely thousands separator
                s = s.replace(',', '')
        
        # Try to convert to float
        return float(s)
        
    except (ValueError, AttributeError) as e:
        logging.debug(f"Failed to parse amount '{value}': {e}")
        return 0.0

def detect_offshore(df):
    """
    Run offshore detection logic on a dataframe.
    Uses vectorized operations where possible for better performance.
    """
    df_copy = df.copy()
    logging.info(f"Processing {len(df_copy)} transactions...")

    # Compute classification data once per row
    df_copy['_classification'] = df_copy.apply(lambda row: analyze_transaction(row), axis=1)

    # Extract classification and explanation in a single pass
    df_copy['Флаг'] = df_copy['_classification'].apply(lambda d: d.get('classification', 'ОФШОР: НЕТ'))
    df_copy['Обоснование'] = df_copy['_classification'].apply(lambda d: d.get('explanation_ru', 'Нет данных'))

    # Clean up helper column
    df_copy.drop(columns=['_classification'], inplace=True)
    return df_copy

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
