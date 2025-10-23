# Offshore Transaction Risk Detection System

Production-ready Python application for detecting offshore jurisdiction involvement in banking transactions for Kazakhstani banks.

## Features

- ✅ **Excel Parsing**: Handles Cyrillic headers with proper skiprows for incoming (row 5) and outgoing (row 6) transactions
- ✅ **Automatic Filtering**: Processes only transactions ≥ 5,000,000 KZT
- ✅ **SWIFT/BIC Analysis**: Extracts country codes from SWIFT codes and validates against offshore list
- ✅ **Simple Fuzzy Matching**: Deterministic matching for country codes, names, and cities (threshold 0.80)
- ✅ **LLM Classification**: OpenAI GPT-4 with structured output and optional web_search tool
- ✅ **Audit Trail**: Comprehensive logging with PII redaction
- ✅ **Web Interface**: Clean FastAPI application for file upload and download
- ✅ **Structured Output**: Pydantic validation ensures consistent JSON schema

## Architecture

```
offshore_detector/
├── main.py                 # Application entrypoint
├── web_app.py             # FastAPI web interface
├── processor.py           # Core processing pipeline
├── schema.py              # Pydantic models for structured output
├── prompts.py             # System Prompt A & B construction
├── llm_client.py          # OpenAI API client with web_search
├── swift_handler.py       # SWIFT/BIC country extraction
├── simple_matcher.py      # Simple fuzzy matching (country/city)
├── excel_handler.py       # Excel parsing and export
├── config.py              # Configuration and environment variables
├── logger.py              # Centralized logging with PII redaction
└── requirements.txt       # Python dependencies
```

## Installation

### Prerequisites

- Python 3.11+
- OpenAI API key

### Setup

1. Clone the repository:
```bash
cd /workspace/offshore_detector
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file from example:
```bash
cp .env.example .env
```

5. Edit `.env` and add your OpenAI API key:
```env
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-4o
DESKTOP_PATH=/path/to/output
THRESHOLD_KZT=5000000.0
```

## Usage

### Web Interface

Start the web application:

```bash
python main.py
```

Then open your browser to `http://localhost:8000`

1. Upload two Excel files (incoming and outgoing transactions)
2. Wait for processing to complete
3. Download the processed files with appended "Результат" column

### API Endpoints

- `GET /` - Web interface
- `POST /upload` - Upload Excel files (returns job_id)
- `GET /status/{job_id}` - Check processing status
- `GET /download/{filename}` - Download processed file
- `GET /health` - Health check endpoint

### Command Line (Advanced)

```python
from processor import process_transactions

files = process_transactions(
    'path/to/incoming.xlsx',
    'path/to/outgoing.xlsx'
)
print(f"Processed files: {files}")
```

## Excel File Format

### Incoming Transactions (skiprows=4)

Headers start at row 5. Required columns (Russian):
- №п/п
- Сумма в тенге
- SWIFT Банка плательщика
- Код страны
- Страна получателя
- Город
- ... (all other columns are preserved)

### Outgoing Transactions (skiprows=5)

Headers start at row 6. Required columns (Russian):
- №п/п
- Сумма в тенге
- SWIFT Банка получателя
- Код страны
- Страна получателя
- Город
- ... (all other columns are preserved)

## Output Format

Processed files preserve ALL original columns and append a **"Результат"** column with the format:

```
Итог: {ОФШОР: ДА|ОФШОР: ПОДОЗРЕНИЕ|ОФШОР: НЕТ} | 
Уверенность: {0-100}% | 
Объяснение: {short Russian explanation} | 
Совпадения: {detected signals} | 
Источники: {web sources if used}
```

Example:
```
Итог: ОФШОР: ДА | Уверенность: 85% | Объяснение: SWIFT код указывает на Каймановы острова | Совпадения: SWIFT:CAYMAN ISLANDS | Источники: нет
```

## LLM Prompts

### System Prompt A - Offshore Jurisdictions

Embeds the full list from `docs/offshore_countries.md` with analysis rules:
1. SWIFT country code is the strongest signal
2. Use simple fuzzy matching for country code/name/city
3. Conservative classification (use OFFSHORE_SUSPECT when uncertain)
4. Must output valid JSON per schema

### System Prompt B - Web Search Permission

Instructs the LLM on web_search tool usage:
- Use for bank domicile verification, SWIFT lookups, regulatory lists
- Cite all sources in the `sources` array
- Keep searches minimal and targeted

## Structured Output Schema

```json
{
  "transaction_id": "string | int | null",
  "direction": "incoming | outgoing",
  "amount_kzt": 5000000.0,
  "signals": {
    "swift_country_code": "KY",
    "swift_country_name": "CAYMAN ISLANDS",
    "is_offshore_by_swift": true,
    "country_name_match": {"value": "CAYMAN ISLANDS", "score": 1.0},
    "country_code_match": {"value": "KY", "score": 1.0},
    "city_match": {"value": null, "score": null}
  },
  "classification": {
    "label": "OFFSHORE_YES",
    "confidence": 0.85
  },
  "reasoning_short_ru": "SWIFT код банка указывает на Каймановы острова",
  "sources": [],
  "llm_error": null
}
```

## Security & Compliance

- ✅ **PII Redaction**: Account numbers redacted in logs (shows only last 4 digits)
- ✅ **Local Processing**: All files processed locally, only LLM API calls external
- ✅ **Path Traversal Protection**: Strict validation on file uploads/downloads
- ✅ **Configurable**: All external endpoints disabled by default except OpenAI
- ✅ **Audit Logging**: Comprehensive structured logs for compliance

## Configuration

All configuration via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | *Required* |
| `OPENAI_MODEL` | Model name | `gpt-4o` |
| `DESKTOP_PATH` | Output directory | `~/Desktop` |
| `UPLOAD_FOLDER` | Upload directory | `/tmp/offshore_uploads` |
| `THRESHOLD_KZT` | Minimum amount | `5000000.0` |
| `PORT` | Web server port | `8000` |
| `HOST` | Web server host | `0.0.0.0` |
| `DEBUG` | Debug mode | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Error Handling

- **LLM Failures**: Falls back to rule-based classification
- **Excel Parse Errors**: Tries multiple skiprows configurations
- **Invalid Files**: Validates extensions and format before processing
- **API Timeouts**: Automatic retry with exponential backoff (3 attempts)

## Logging

Structured JSON logging with PII redaction:

```json
{
  "row": 42,
  "direction": "incoming",
  "swift_country": "CAYMAN ISLANDS",
  "swift_offshore": true,
  "prelim_conf": 0.7,
  "final_class": "ОФШОР: ДА",
  "final_conf": 0.85,
  "sources_count": 0,
  "ms": {"geocode": 0, "openai": 1523, "total": 1530}
}
```

## Testing

Run a test classification:

```bash
python -c "
from processor import process_transactions
files = process_transactions('test_incoming.xlsx', 'test_outgoing.xlsx')
print(f'Output: {files}')
"
```

## Deployment

### Docker (Recommended)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
CMD ["python", "main.py"]
```

Build and run:
```bash
docker build -t offshore-detector .
docker run -p 8000:8000 -e OPENAI_API_KEY=xxx offshore-detector
```

### Production Recommendations

1. **Use environment variables** for all secrets (never commit `.env`)
2. **Enable HTTPS** via reverse proxy (nginx, traefik)
3. **Set `DEBUG=false`** in production
4. **Configure `DESKTOP_PATH`** to persistent storage
5. **Monitor logs** for errors and performance
6. **Set resource limits** (memory, CPU)
7. **Use `LOG_LEVEL=WARNING`** in production to reduce noise

## Troubleshooting

### "OpenAI API key not found"
- Ensure `OPENAI_API_KEY` is set in `.env`
- Check that `.env` file is in the same directory as `main.py`

### "Failed to parse Excel file"
- Verify the file format (must be .xlsx or .xls)
- Check that headers are at the expected rows (row 5 for incoming, row 6 for outgoing)
- Ensure "Сумма в тенге" column exists

### "DESKTOP_PATH not writable"
- Check directory permissions
- Create the directory if it doesn't exist
- Set `DESKTOP_PATH` to a valid writable path

## License

Proprietary - Internal use only

## Support

For issues and questions, contact the development team.
