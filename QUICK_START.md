# Quick Start Guide

## Get Running in 3 Steps

### Step 1: Configure Environment

```bash
cd offshore_detector
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:
```env
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o
DESKTOP_PATH=/tmp/offshore_outputs
```

### Step 2: Install & Run

**Option A: Using the startup script (recommended)**
```bash
./run.sh
```

**Option B: Manual setup**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

**Option C: Docker**
```bash
cd ..
docker-compose up --build
```

### Step 3: Use the Application

1. Open browser to: **http://localhost:8000**
2. Upload two Excel files:
   - Incoming transactions (headers at row 5)
   - Outgoing transactions (headers at row 6)
3. Wait for processing (progress shown on page)
4. Download processed files with "Результат" column

## Expected Input Format

### Incoming Transactions Excel

- **Headers start**: Row 5 (use `skiprows=4` in pandas)
- **Required columns** (Russian):
  - №п/п
  - Сумма в тенге (must be ≥ 5,000,000 KZT)
  - SWIFT Банка плательщика
  - Код страны
  - Страна получателя
  - Город

### Outgoing Transactions Excel

- **Headers start**: Row 6 (use `skiprows=5` in pandas)
- **Required columns** (Russian):
  - №п/п
  - Сумма в тенге (must be ≥ 5,000,000 KZT)
  - SWIFT Банка получателя
  - Код страны
  - Страна получателя
  - Город

## Expected Output Format

All original columns preserved, plus a new **"Результат"** column:

```
Итог: ОФШОР: ДА | Уверенность: 85% | Объяснение: SWIFT код указывает на Каймановы острова | Совпадения: SWIFT:CAYMAN ISLANDS | Источники: нет
```

## Troubleshooting

### "OpenAI API key not found"
- Check that `OPENAI_API_KEY` is set in `.env`
- Ensure `.env` file is in the `offshore_detector` directory

### "Failed to parse Excel file"
- Verify file extension is `.xlsx` or `.xls`
- Check that headers are at the correct row (5 for incoming, 6 for outgoing)
- Ensure "Сумма в тенге" column exists

### "No transactions meet threshold"
- Check that "Сумма в тенге" values are ≥ 5,000,000
- Verify amount formatting (remove currency symbols, use numbers only)

### Application won't start
- Ensure Python 3.11+ is installed: `python3 --version`
- Check that port 8000 is not already in use: `lsof -i :8000`
- Review logs for error messages

## Testing with Sample Data

Create a simple test Excel file:

1. Create Excel with headers at row 5 (incoming) or row 6 (outgoing)
2. Add columns: №п/п, Сумма в тенге, SWIFT Банка плательщика, etc.
3. Add test row with amount ≥ 5,000,000
4. Add SWIFT code from offshore jurisdiction (e.g., `ABCAKYXX` for Cayman Islands)
5. Upload and verify output includes offshore detection

## Next Steps

- Read full documentation: `offshore_detector/README.md`
- Review implementation details: `IMPLEMENTATION_SUMMARY.md`
- Check API endpoints: http://localhost:8000/docs (FastAPI auto-generated)
- Monitor logs for processing details

## Support

For issues:
1. Check logs in console output
2. Verify environment configuration in `.env`
3. Review error messages in the web interface
4. Check `IMPLEMENTATION_SUMMARY.md` for technical details

## Production Deployment

Before deploying to production:

1. **Security**:
   - Set strong `SECRET_KEY` in environment
   - Use HTTPS (configure reverse proxy)
   - Restrict network access to authorized IPs
   - Enable firewall rules

2. **Configuration**:
   - Set `DEBUG=false`
   - Use `LOG_LEVEL=WARNING` or `ERROR`
   - Configure `DESKTOP_PATH` to persistent storage
   - Set appropriate resource limits

3. **Monitoring**:
   - Set up log aggregation
   - Monitor API response times
   - Track LLM API usage and costs
   - Set up health check alerts

4. **Backup**:
   - Regular backups of output directory
   - Backup configuration files
   - Document environment variables

Ready to go! 🚀
