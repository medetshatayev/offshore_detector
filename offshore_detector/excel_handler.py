"""
Excel parsing and export functionality.
"""
import pandas as pd
import os
from config import DESKTOP_PATH

def parse_excel(file_path, direction):
    """
    Parse incoming or outgoing transaction Excel files, trying different skiprows values.
    """
    skip_options = [4, 3, 5] if direction == 'incoming' else [5, 4, 6]

    for skips in skip_options:
        try:
            df = pd.read_excel(file_path, skiprows=skips)
            if 'Сумма в тенге' in df.columns or 'Сумма' in df.columns:
                return df
        except Exception:
            continue
    
    raise ValueError(f"Failed to parse {file_path} with any of the tried skip row configurations.")

def export_to_excel(df, filename, sheet_name):
    """
    Export dataframe to an Excel file on the desktop.
    """
    if not os.path.exists(DESKTOP_PATH):
        os.makedirs(DESKTOP_PATH)
    
    output_path = os.path.join(DESKTOP_PATH, filename)
    
    # Drop temporary columns before exporting
    df_to_export = df.drop(columns=['amount_kzt_normalized', 'direction', 'timestamp'], errors='ignore')

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_to_export.to_excel(writer, sheet_name=sheet_name, index=False)
