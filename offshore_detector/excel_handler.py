"""
Excel parsing and export functionality.
"""
import pandas as pd
import os
import logging
from config import DESKTOP_PATH

def parse_excel(file_path, direction):
    """
    Parse incoming or outgoing transaction Excel files.
    Tries different skiprows values to handle various file formats.
    
    Args:
        file_path: Path to the Excel file
        direction: 'incoming' or 'outgoing'
    
    Returns:
        DataFrame with parsed transaction data
    
    Raises:
        ValueError: If file cannot be parsed with any configuration
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    skip_options = [4, 3, 5] if direction == 'incoming' else [5, 4, 6]
    required_columns = ['Сумма в тенге', 'Сумма']

    for skips in skip_options:
        try:
            df = pd.read_excel(file_path, skiprows=skips)
            
            # Check if any of the required columns exist
            if any(col in df.columns for col in required_columns):
                logging.info(f"Successfully parsed {file_path} ({direction}) with skiprows={skips}")
                return df
                
        except Exception as e:
            logging.debug(f"Failed to parse {file_path} with skiprows={skips}: {e}")
            continue
    
    raise ValueError(
        f"Failed to parse {file_path} with any skip row configuration. "
        f"Tried: {skip_options}. Required columns: {required_columns}"
    )

def export_to_excel(df, filename, sheet_name):
    """
    Export dataframe to an Excel file on the desktop.
    Preserves all original columns and appends the "Результат" column.
    
    Args:
        df: DataFrame to export (must contain "Результат" column)
        filename: Output filename
        sheet_name: Name of the Excel sheet
    
    Raises:
        OSError: If unable to create directory or write file
        ValueError: If DESKTOP_PATH is not configured
    
    Note:
        Returns early (no file created) if df is None or empty.
        Calling code should handle this gracefully.
    """
    if df is None or df.empty:
        logging.warning(f"Attempted to export empty dataframe to {filename}. No file created.")
        return
    
    # Validate DESKTOP_PATH is configured
    if not DESKTOP_PATH:
        raise ValueError("DESKTOP_PATH is not configured. Cannot export files.")
    
    # Ensure output directory exists and is writable
    try:
        os.makedirs(DESKTOP_PATH, exist_ok=True)
        
        # Test if directory is writable
        if not os.access(DESKTOP_PATH, os.W_OK):
            raise OSError(f"DESKTOP_PATH '{DESKTOP_PATH}' is not writable")
            
    except OSError as e:
        logging.error(f"Failed to create/access output directory {DESKTOP_PATH}: {e}")
        raise
    
    output_path = os.path.join(DESKTOP_PATH, filename)
    
    # Drop temporary/internal columns before exporting
    temp_columns = ['amount_kzt_normalized', 'direction', 'processed_at', 'row_index']
    df_to_export = df.drop(columns=temp_columns, errors='ignore')

    try:
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df_to_export.to_excel(writer, sheet_name=sheet_name, index=False)
        logging.info(f"Successfully exported {len(df_to_export)} rows to {output_path}")
    except Exception as e:
        logging.error(f"Failed to export to {output_path}: {e}")
        raise
