"""
Excel parsing and export functionality.
"""
import pandas as pd
import os
from config import DESKTOP_PATH

def parse_excel(file_path, direction):
    """
    Parse incoming or outgoing transaction Excel files.
    """
    skiprows = 4 if direction == 'incoming' else 5
    try:
        return pd.read_excel(file_path, skiprows=skiprows)
    except Exception as e:
        raise ValueError(f"Failed to parse {file_path}: {e}")

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
