# Copilot project instructions for AI coding agents

Purpose and architecture
- This is a Flask web app for detecting offshore-risk transactions from bank Excel exports.
- User uploads two Excel files (incoming, outgoing) at `/`.
- Pipeline: `offshore_detector.process_transactions()` →
  1) Parse Excel: `excel_handler.parse_excel()` (handles varying header offsets).
  2) Normalize + filter by amount (KZT): `offshore_detector.filter_transactions()` using `THRESHOLD_KZT`.
  3) Per-row analysis: `analyzer.analyze_transaction()` → preliminary signals (fuzzy jurisdiction hits, SWIFT country), geocoding via OSM, GPT classification via `ai_classifier.classify_with_gpt4()` with fallback.
  4) Export two processed Excel files to `DESKTOP_PATH` via `excel_handler.export_to_excel()`.
- UI polls job state (in-memory `jobs` dict) and serves downloads from `DESKTOP_PATH` using `/download/<filename>`.

Key files
- `offshore_detector/app.py`: Flask app, upload handling, threading job runner, download endpoint, file cleanup and extension checks.
- `offshore_detector/offshore_detector.py`: Orchestrates end-to-end processing; filtering and result export.
- `offshore_detector/analyzer.py`: Core per-row logic (fuzzy matching, SWIFT parse, confidence scoring, GPT call + logging).
- `offshore_detector/ai_classifier.py`: OpenAI Responses API (model `gpt-4.1`, optional `web_search` tool). Applies "confidence hygiene" and robust JSON parsing.
- `offshore_detector/web_research.py`: OSM Nominatim geocoding with rate limiting, caching, and bank-name normalization.
- `offshore_detector/fuzzy_matcher.py`: Levenshtein-based matcher with token/stopword heuristics.
- `offshore_detector/excel_handler.py`: Flexible Excel parsing; exports to Desktop; drops temp columns before write.
- `offshore_detector/config.py`: Env/config: `OPENAI_API_KEY`, `DESKTOP_PATH`, `THRESHOLD_KZT`, jurisdiction lists, SWIFT map, field weights, scenario labels.
- Docs: `docs/offshore_countries.md`, `docs/offshore_transaction_scenarios.md` describe country lists and scenarios.

Conventions and data model
- Input columns are Russian (e.g., `Сумма в тенге`, `Плательщик`, `Банк получателя`, `SWIFT Банка плательщика`). Keep these exact headers in parsing/analysis.
- Temporary columns added during processing: `amount_kzt_normalized`, `direction`, `timestamp` — removed before export.
- Output columns added: `Флаг` (classification) and `Обоснование` (Russian explanation from GPT/fallback).
- Scenarios: 1=Входящий из офшора, 2=Исходящий в офшор, 3=Операции с офшорными лицами.
- Amount parsing supports mixed locales; see `_parse_amount()` for rules.

External integrations
- OpenAI: Requires `OPENAI_API_KEY`. If missing, `fallback_classification()` uses preliminary confidence only. Model and tool usage defined in `ai_classifier.py`.
- Geocoding: OpenStreetMap Nominatim (rate-limited to ~1 req/sec, cached). Bank-name normalization includes aliases (e.g., HSBC, Metrobank).

Local development
- Python: 3.12. Install deps: `pip install -r offshore_detector/requirements.txt`.
- Run app (dev): from `offshore_detector/` folder: `FLASK_ENV=development python app.py` (loads `.env` via `dotenv`).
- Docker: `docker compose up --build` serves on http://localhost:8081 (Gunicorn, gevent). Uploads stored in `offshore_detector/uploads` (mounted volume).
- Env: Copy `.env.example` to `.env` in `offshore_detector/`. Ensure `DESKTOP_PATH` exists inside your runtime (container or host) for exports.

Common extension points
- Add jurisdictions: edit `OFFSHORE_JURISDICTIONS` and `SWIFT_COUNTRY_MAP` in `config.py`.
- Tune thresholds/weights: `THRESHOLD_KZT`, `FIELD_WEIGHTS_INCOMING/OUTGOING` in `config.py`.
- Adjust Excel parsing: update `skip_options` and `required_columns` in `excel_handler.parse_excel()`.
- Enrich output: modify `detect_offshore()` in `offshore_detector.py` to add columns before export.
- Geocoding tweaks: extend `_normalize_bank_query()` aliases or `bank_home_countries` in `web_research.py`.

Operational notes
- Jobs are in-memory and per-process; not persistent across restarts.
- Download endpoint serves from `DESKTOP_PATH`. In Docker, this path is inside the container unless you bind-mount it.
- Logs: Structured info logs summarize row analysis and OpenAI responses; PII is truncated but may appear in geocoding logs.

Safety and validations
- File uploads restricted to `.xlsx/.xls` with `werkzeug.secure_filename` and cleanup after processing.
- SWIFT parsing validates length and alphabetic country codes. Fuzzy matcher uses stopwords and multi-signal gating to reduce false positives.

Ask before changing
- Column header names, Russian labels, or scenario numbering — these are business-coupled. Confirm before refactors.
