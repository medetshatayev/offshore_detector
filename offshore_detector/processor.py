"""
Core transaction processing pipeline.
Orchestrates parsing, filtering, analysis, and export.
"""
import pandas as pd
from datetime import datetime
import logging
from typing import List, Tuple

from excel_handler import parse_excel, export_to_excel
from swift_handler import extract_swift_country
from simple_matcher import get_all_matches
from llm_client import classify_transaction, format_result_column
from config import THRESHOLD_KZT


def normalize_amount(value) -> float:
    """
    Parse and normalize amount from various formats.
    Handles spaces, commas, periods as thousands/decimal separators.
    
    Args:
        value: Amount value (can be float, int, or string)
    
    Returns:
        Normalized float value, or 0.0 if parsing fails
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
        
        return float(s)
        
    except (ValueError, AttributeError) as e:
        logging.debug(f"Failed to parse amount '{value}': {e}")
        return 0.0


def filter_and_enrich(df: pd.DataFrame, direction: str) -> pd.DataFrame:
    """
    Filter transactions by amount threshold and add metadata.
    
    Args:
        df: DataFrame with transaction data
        direction: 'incoming' or 'outgoing'
    
    Returns:
        Filtered DataFrame with normalized amounts and metadata
    """
    # Add metadata
    df = df.copy()
    df['direction'] = direction
    df['processed_at'] = datetime.now()
    df['row_index'] = df.index
    
    # Normalize amount
    df['amount_kzt_normalized'] = df['Сумма в тенге'].apply(normalize_amount)
    
    # Filter by threshold
    df_filtered = df[df['amount_kzt_normalized'] >= THRESHOLD_KZT].copy()
    
    logging.info(
        f"Filtered {direction} transactions: {len(df_filtered)} of {len(df)} "
        f"meet threshold of {THRESHOLD_KZT:,.0f} KZT"
    )
    
    return df_filtered


def analyze_transaction_row(row: pd.Series) -> str:
    """
    Analyze a single transaction row and return the formatted result string.
    
    Args:
        row: Pandas Series with transaction data
    
    Returns:
        Formatted result string for "Результат" column
    """
    try:
        # Extract relevant fields based on direction
        direction = row.get('direction')
        
        if direction == 'incoming':
            swift_code = row.get('SWIFT Банка плательщика')
            country_code = row.get('Код страны')
            country_name = row.get('Страна получателя')  # This might be sender's country
            city = row.get('Город')
        else:  # outgoing
            swift_code = row.get('SWIFT Банка получателя')
            country_code = row.get('Код страны')
            country_name = row.get('Страна получателя')
            city = row.get('Город')
        
        # 1. Extract SWIFT country
        swift_info = extract_swift_country(swift_code) if swift_code else None
        
        # 2. Get fuzzy matching signals
        fuzzy_matches = get_all_matches(
            country_code=country_code,
            country_name=country_name,
            city=city
        )
        
        # 3. Build local signals dict
        local_signals = {
            'swift': swift_info or {},
            **fuzzy_matches
        }
        
        # 4. Convert row to dict for LLM
        transaction_data = row.to_dict()
        
        # 5. Call LLM for classification
        classification = classify_transaction(transaction_data, local_signals)
        
        # 6. Format result string
        result_str = format_result_column(classification)
        
        return result_str
        
    except Exception as e:
        logging.error(f"Error analyzing transaction at row {row.get('№п/п', 'unknown')}: {e}", 
                     exc_info=True)
        return f"ОШИБКА: {str(e)}"


def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Process all transactions in a dataframe.
    Adds "Результат" column with classification results.
    
    Args:
        df: Filtered DataFrame with transactions to process
    
    Returns:
        DataFrame with added "Результат" column
    """
    logging.info(f"Processing {len(df)} transactions...")
    
    # Apply analysis to each row
    df['Результат'] = df.apply(analyze_transaction_row, axis=1)
    
    logging.info(f"Completed processing {len(df)} transactions")
    
    return df


def process_transactions(incoming_file_path: str, outgoing_file_path: str) -> List[str]:
    """
    Main processing pipeline for offshore transaction detection.
    
    Args:
        incoming_file_path: Path to incoming transactions Excel file
        outgoing_file_path: Path to outgoing transactions Excel file
    
    Returns:
        List of output filenames created
    """
    logging.info("=" * 80)
    logging.info("Starting offshore transaction detection pipeline")
    logging.info("=" * 80)
    
    # 1. Parse Excel files
    logging.info("Step 1: Parsing Excel files...")
    incoming_df = parse_excel(incoming_file_path, 'incoming')
    outgoing_df = parse_excel(outgoing_file_path, 'outgoing')
    logging.info(f"Parsed {len(incoming_df)} incoming and {len(outgoing_df)} outgoing transactions")
    
    # 2. Filter and enrich
    logging.info("Step 2: Filtering by amount threshold...")
    incoming_filtered = filter_and_enrich(incoming_df, 'incoming')
    outgoing_filtered = filter_and_enrich(outgoing_df, 'outgoing')
    
    # 3. Process transactions (analyze + classify)
    logging.info("Step 3: Analyzing and classifying transactions...")
    incoming_processed = process_dataframe(incoming_filtered)
    outgoing_processed = process_dataframe(outgoing_filtered)
    
    # 4. Export results
    logging.info("Step 4: Exporting results to Excel...")
    now = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    
    incoming_filename = f"incoming_transactions_processed_{now}.xlsx"
    outgoing_filename = f"outgoing_transactions_processed_{now}.xlsx"
    
    export_to_excel(incoming_processed, incoming_filename, "Входящие операции")
    export_to_excel(outgoing_processed, outgoing_filename, "Исходящие операции")
    
    logging.info("=" * 80)
    logging.info("Pipeline completed successfully")
    logging.info(f"Output files: {incoming_filename}, {outgoing_filename}")
    logging.info("=" * 80)
    
    return [incoming_filename, outgoing_filename]
