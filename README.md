# Offshore Transaction Risk Detection System

Production-ready system for detecting offshore jurisdiction involvement in banking transactions for Kazakhstani banks.

## Quick Start

### Using Docker (Recommended)

1. Create environment file:
```bash
cd offshore_detector
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

2. Build and run:
```bash
docker-compose up --build
```

3. Open browser to: http://localhost:8000

### Local Development

1. Install dependencies:
```bash
cd offshore_detector
./run.sh
```

2. Or manually:
```bash
cd offshore_detector
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Documentation

See `offshore_detector/README.md` for detailed documentation.

## Project Structure

- `offshore_detector/` - Main application code
- `docs/` - Documentation and reference data
- `Dockerfile` - Docker container configuration
- `docker-compose.yml` - Docker Compose setup

## Features

- Excel file upload and processing
- SWIFT/BIC country code extraction
- Simple fuzzy matching for offshore jurisdictions
- OpenAI GPT-4 classification with web_search
- Structured output with pydantic validation
- Comprehensive logging with PII redaction

## Requirements

- Python 3.11+
- OpenAI API key
- Excel files with Cyrillic headers

## License

Proprietary - Internal use only
