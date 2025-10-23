"""
Configuration and constants for the Offshore Transaction Risk Detection System.
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-5')  # Responses API default

# File Paths
DESKTOP_PATH = os.getenv('DESKTOP_PATH', os.path.join(os.path.expanduser('~'), 'Desktop'))
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/tmp/offshore_uploads')

# Processing Configuration
THRESHOLD_KZT = float(os.getenv('THRESHOLD_KZT', 5000000.0))

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
