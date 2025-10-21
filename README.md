# Offshore Transaction Risk Detection System

## Overview
This project is a web-based system for detecting and classifying the risk of offshore transactions in financial data, tailored for Kazakhstan regulatory requirements. It processes incoming and outgoing transaction Excel files, analyzes each transaction for offshore risk, and produces annotated Excel reports with detailed risk assessments.

## Main Logic Flow

### 1. **User Uploads Transaction Files**
- The user uploads two Excel files: one for incoming transactions and one for outgoing transactions via the web interface (`app.py`).
- Files are saved to the `uploads/` directory.

### 2. **Processing Pipeline** (`offshore_detector.py`)
- The main function `process_transactions` orchestrates the pipeline:
    1. **Parsing**: Reads Excel files using `parse_excel` from `excel_handler.py`.
    2. **Filtering**: Filters transactions by amount (default threshold: 5,000,000 KZT, configurable in `.env` or `config.py`).
    3. **Offshore Detection**: Each transaction is analyzed for offshore risk using `detect_offshore`, which applies the core logic from `analyzer.py`.
    4. **Exporting**: Results are exported to new Excel files on the user's Desktop, with risk annotations.

### 3. **Transaction Analysis** (`analyzer.py`)
- For each transaction (row):
    1. **Preliminary Analysis** (`run_preliminary_analysis`):
        - **Dictionary Matching**: Fuzzy matches transaction fields (e.g., counterparty, bank, address, country) against lists of known offshore jurisdictions (in Russian and English).
        - **SWIFT Code Analysis**: Extracts country from SWIFT code and checks if it is offshore.
        - **Confidence Calculation**: Assigns a confidence score based on the number and type of matches.
        - **Scenario Classification**: Assigns a scenario (1: incoming, 2: outgoing, 3: other) based on direction and matches.
    2. **Web Research** (if confidence > 0.2):
        - Runs parallel web research (geocoding and Google search) for additional evidence.
    3. **AI Classification** (`ai_classifier.py`):
        - Sends transaction data and preliminary analysis to OpenAI GPT for final classification and explanation (if API key is set).
        - If GPT is unavailable, falls back to rule-based classification.

### 4. **Result Formatting**
- Each transaction receives a result string summarizing:
    - Final classification (ОФШОР: ДА/ПОДОЗРЕНИЕ/НЕТ)
    - Scenario and description
    - Confidence score
    - Explanation (in Russian)
    - Matched fields and sources
- Results are written to Excel files for both incoming and outgoing transactions.

## Key Files and Their Roles
- `app.py`: Flask web app for file upload, job management, and result download.
- `offshore_detector.py`: Main processing pipeline.
- `analyzer.py`: Core transaction analysis logic.
- `ai_classifier.py`: GPT integration for advanced classification.
- `excel_handler.py`: Excel file parsing and export.
- `fuzzy_matcher.py`: Fuzzy string matching for offshore detection.
- `web_research.py`: Web research (geocoding, Google search) for additional evidence.
- `config.py`: Configuration, constants, and jurisdiction lists.

## Configuration
- `.env` file (optional):
    - `OPENAI_API_KEY`: For GPT-4 classification.
    - `THRESHOLD_KZT`: Minimum transaction amount for analysis.
    - `DESKTOP_PATH`: Where to save result files.

## How to Use
1. Start the Flask app (`python app.py`).
2. Open the web interface in your browser.
3. Upload the required Excel files for incoming and outgoing transactions.
4. Wait for processing to complete (status shown on the page).
5. Download the processed Excel files with risk annotations from your Desktop.

## Logic Details
- **Filtering**: Only transactions above the threshold are analyzed.
- **Fuzzy Matching**: Uses Levenshtein distance and token matching to detect offshore-related terms in key fields.
- **SWIFT Analysis**: Extracts country from SWIFT code and checks against offshore list.
- **Confidence Scoring**: Weighted by field importance and number of matches.
- **AI Classification**: GPT-4 provides nuanced classification and explanations, using all available evidence.
- **Web Research**: Adds external evidence for higher-confidence cases.

## Extensibility
- Add new offshore jurisdictions in `config.py`.
- Adjust field weights and thresholds as needed.
- Integrate additional data sources or APIs for enhanced detection.

## Security & Privacy
- Uploaded files are processed locally and not stored long-term.
- API keys and sensitive data should be managed via environment variables.

---

For more details, see the docstrings in each module.
