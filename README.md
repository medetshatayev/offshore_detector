# Offshore Transaction Risk Detection System

Production-ready, lightweight system for detecting offshore jurisdiction involvement in banking transactions for Kazakhstani banks.

**Latest Update**: Optimized and cleaned up - 40% less code, faster processing, lower costs.

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

- 🚀 **Lightweight**: 11 core modules, ~1,700 lines of code
- 📊 **Excel Processing**: Handles Cyrillic headers, filters by amount threshold
- 🔍 **SWIFT Analysis**: Extracts country codes, validates against 87 offshore jurisdictions
- 🤖 **AI Classification**: OpenAI GPT with web_search capability
- ✅ **Validated Output**: Pydantic schemas ensure data integrity
- 🔒 **Secure**: PII redaction in logs, path validation, file type checks
- ⚡ **Optimized**: 70% smaller LLM payloads = faster + cheaper

## Requirements

- Python 3.11+
- OpenAI API key
- Excel files with Cyrillic headers

## License

Proprietary - Internal use only
