# Offshore Transaction Risk Detection System — Technical Documentation

This document provides a comprehensive, implementation-level overview of the project located in this repository. It covers architecture, data flow, components, algorithms, configuration, deployment, and operational considerations.

## 1) Purpose and Scope
A Flask-based web application that detects and classifies offshore risk in financial transactions (Kazakhstan regulatory focus). Users upload two Excel files (incoming and outgoing transactions); the system analyzes each transaction and produces annotated Excel outputs with explanations and confidence scores.

## 2) High-Level Architecture
- Web UI and HTTP server: `flask` app in `offshore_detector/app.py`
- Processing pipeline orchestrator: `offshore_detector/offshore_detector.py`
- Core analysis and risk scoring: `offshore_detector/analyzer.py`
- AI-based classification (OpenAI): `offshore_detector/ai_classifier.py`
- Excel I/O: `offshore_detector/excel_handler.py`
- Fuzzy matching: `offshore_detector/fuzzy_matcher.py`
- Web research (geocoding, search): `offshore_detector/web_research.py`
- Configuration and constants: `offshore_detector/config.py`
- UI template: `offshore_detector/templates/index.html`
- Containerization: `Dockerfile`, `docker-compose.yml`

Sequence (happy path):
1. User uploads two Excel files.
2. `app.py` stores files in `uploads/`, starts a background thread.
3. Thread calls `process_transactions(...)` in `offshore_detector.py`.
4. `parse_excel(...)` reads input files, `filter_transactions(...)` normalizes and filters by amount.
5. Each row analyzed via `analyze_transaction(...)` -> preliminary signals -> optional web research -> GPT classification (or fallback).
6. Results exported to Excel on the configured Desktop path; UI exposes download links.

## 3) Web Application (`app.py`)
- Routes:
  - `/` GET/POST: upload form; job status view.
  - `/reload`: resets session job.
  - `/download/<filename>`: serves processed files from `DESKTOP_PATH` using `send_from_directory` with path traversal protection.
- Upload constraints:
  - File size limit: 50 MB (`MAX_CONTENT_LENGTH`).
  - Allowed extensions: `.xlsx`, `.xls`.
- Jobs:
  - In-memory job store `jobs` keyed by `job_id` (session-kept).
  - Background processing via `threading.Thread` in `process_transactions_wrapper`.
  - Cleans up uploaded files after processing.
- Security and reliability:
  - Secret key from `SECRET_KEY` env (dev fallback present).
  - Basic filename sanitization with `os.path.basename`.
  - No auth/CSRF by design (internal tool assumption).

## 4) Processing Pipeline (`offshore_detector.py`)
- `process_transactions(incoming_path, outgoing_path)`
  - Parses Excel files with `parse_excel`.
  - `filter_transactions(df, direction)`:
    - Adds `amount_kzt_normalized` via robust `parse_amount` handling commas, dots, spaces.
    - Adds `direction` and `timestamp`.
    - Filters by `THRESHOLD_KZT` from env.
  - `detect_offshore(df)`:
    - Row-wise `apply` calls `analyze_transaction(row)` and formats final string.
  - `export_results(...)` writes two Excel files to `DESKTOP_PATH` (timestamped names) via `export_to_excel`.
- Result formatting combines classification, scenario, confidence, explanation, matched fields, and sources.

## 5) Core Analysis (`analyzer.py`)
- `analyze_transaction(row)`:
  - `run_preliminary_analysis(row)` computes:
    - Dictionary hits: fuzzy matching of row fields against `OFFSHORE_JURISDICTIONS` (English/Russian lists).
    - SWIFT country extraction: positions 4:6 -> `SWIFT_COUNTRY_MAP` -> checks if offshore.
    - Matched fields and match details for confidence.
    - Scenario classification (1 incoming, 2 outgoing, 3 generic when signals present).
    - Confidence score aggregation (see formula below).
  - If preliminary confidence > 0.2, runs `parallel_web_research(counterparty, bank)` to enrich signals with geocoding and search links.
  - Calls `classify_with_gpt4(row, preliminary_analysis)` for structured final decision.
  - Any exception yields a structured "ОШИБКА" result.

- Confidence aggregation (bounded to [0,1]):
  - Base signals: +0.3 if any dict hit; +0.2 if SWIFT offshore match.
  - Field-weighted signals (scaled): sum of field weights (by direction) × 0.3, capped at 0.3.
  - Multiplicity bonuses: +0.05 if >1 dict hit; +0.05 if >2 matched fields.
  - Fuzzy similarity: average similarity × 0.1.

Mathematically:

$$
\begin{aligned}
C &= \min\bigg(\, 0.3\,\mathbb{1}[\text{dict\_hits}>0] + 0.2\,\mathbb{1}[\text{swift\_match}] \\
  &\quad + 0.3\,\min\{1, \sum_{f\in F_\text{matched}} w_f\} \\
  &\quad + 0.05\,\mathbb{1}[\lvert\text{dict\_hits}\rvert>1] + 0.05\,\mathbb{1}[\lvert F_\text{matched}\rvert>2] \\
  &\quad + 0.1\,\overline{s}\, ,\; 1\bigg)
\end{aligned}
$$

where $\overline{s}$ is the average fuzzy similarity and $w_f$ comes from `FIELD_WEIGHTS_INCOMING` or `FIELD_WEIGHTS_OUTGOING`.

- Scenario mapping in `classify_scenario(direction, dict_hits, swift_country_match)`:
  - If any signal present and direction is incoming: 1.
  - If any signal present and direction is outgoing: 2.
  - Otherwise, if signals present but direction unknown: 3.

## 6) AI Classifier (`ai_classifier.py`)
- Uses `openai` client with `OPENAI_API_KEY` to call `chat.completions.create` on model `gpt-4.1`.
- System prompt enforces a strict JSON schema for response with fields:
  - `classification`, `scenario`, `confidence`, `matched_fields`, `signals`, `sources`, `explanation_ru`.
- Cleans code fences and parses JSON; on any error or missing API key, falls back to `fallback_classification(preliminary_analysis)` which maps confidence to three buckets:
  - > 0.7 → "ОФШОР: ДА"
  - > 0.3 → "ОФШОР: ПОДОЗРЕНИЕ"
  - else → "ОФШОР: НЕТ"

## 7) Fuzzy Matching (`fuzzy_matcher.py`)
- Normalization: lowercasing, punctuation removal, and trim.
- Strategies (returns up to top 5 unique matches with similarity):
  - Exact substring → similarity 1.0.
  - Token-level exact match → 0.95.
  - Levenshtein-based similarity:
    - For short strings, full-text Levenshtein.
    - For long strings, token-wise best-pair similarity.
- Dependency: `python-Levenshtein`.

## 8) Web Research (`web_research.py`)
- `geocode_bank(name)` via OpenStreetMap Nominatim (1 req/sec rate limit, cached via `lru_cache`, retries via `tenacity`).
- `google_search(counterparty, bank)` scrapes top links from Google result page (rate-limited, cached; note reliability and ToS considerations). Returns up to 3 links.
- `parallel_web_research(...)` runs geocoding and search concurrently with safe event loop handling (works in normal app and notebook contexts).

## 9) Excel Handling (`excel_handler.py`)
- `parse_excel(file_path, direction)`:
  - Tries several `skiprows` heuristics based on direction to accommodate varying report headers.
  - Accepts files having at least `Сумма в тенге` or `Сумма` column.
- `export_to_excel(df, filename, sheet_name)`:
  - Drops helper columns: `amount_kzt_normalized`, `direction`, `timestamp`.
  - Writes to `DESKTOP_PATH/filename` via `openpyxl`.

## 10) Configuration (`config.py`)
- Env and defaults:
  - `OPENAI_API_KEY`, `DESKTOP_PATH` (default: user's Desktop), `THRESHOLD_KZT` (default 5,000,000).
- Dictionaries and weights:
  - `OFFSHORE_JURISDICTIONS`: English and Russian jurisdiction lists.
  - `SWIFT_COUNTRY_MAP`: ISO country code → offshore country name.
  - Field weights per direction; field name translations for UI; scenario descriptions.
- Example env file: `offshore_detector/.env.example`.

## 11) UI (`templates/index.html`)
- Bootstrap 4 single-page flow:
  - Upload form (two files).
  - Status area (processing/completed/failed) based on `job_info`.
  - Download links for generated Excel files.

## 12) Containerization and Runtime
- `Dockerfile`:
  - Base: `python:3.12-slim`.
  - Installs requirements from `offshore_detector/requirements.txt`.
  - Runs `gunicorn` with `gevent` worker on `0.0.0.0:8081`.
- `docker-compose.yml`:
  - Maps port 8081.
  - Mounts `./offshore_detector/uploads` to `/app/uploads` for temporary uploads.
- Note on `DESKTOP_PATH` in containers:
  - Outputs are written to `DESKTOP_PATH`. In Docker, set `DESKTOP_PATH` to a host-mounted volume if you want direct host access to files. Otherwise, the `/download/<filename>` route in the container must point to a path available inside the container.

## 13) Operational Concerns
- Security:
  - Basic filename and path traversal protections; size and extension checks.
  - No authentication/authorization; no CSRF protection (assumed internal use).
  - External scraping of Google may violate ToS and can be blocked; consider paid search APIs.
- Performance:
  - Row-wise `df.apply(...)` is single-threaded; for large datasets, consider `concurrent.futures` with chunking or vectorized pre-filters, or multiprocessing.
  - OpenAI calls can be rate-limited; consider caching results per counterparty/bank and batching.
  - Web research already uses caching and rate limiting.
- Reliability:
  - In-memory job store; for production use Redis or a DB and a task queue (Celery/RQ) for retries and persistence.
  - Add structured logging and request IDs.

## 14) Expected Columns and Data Assumptions
Typical columns referenced:
- Parties/banks: `Плательщик`, `Получатель`, `Банк плательщика`, `Банк получателя`, `Адрес банка плательщика`, `Адрес банка получателя`.
- Identifiers: `SWIFT Банка плательщика`, `SWIFT Банка получателя`.
- Geo: `Страна резидентства`, `Город`.
- Payments: `Сумма в тенге` (or `Сумма`), `Детали платежа`.

## 15) Logging and Errors
- Basic logging configured in `offshore_detector.py` (INFO level with timestamps).
- Exceptions are caught in analysis and classification, with graceful fallback and error messages routed to UI when jobs fail.

## 16) How to Run
- Local with Docker:
  - Create `.env` (see `offshore_detector/.env.example`) and ensure `OPENAI_API_KEY`/`DESKTOP_PATH`/`THRESHOLD_KZT` as needed.
  - `docker-compose up --build`
  - Open http://localhost:8081
- Direct (not recommended when repo is containerized): ensure Python 3.12, install `offshore_detector/requirements.txt`, set envs, run `gunicorn` similar to the Dockerfile.

## 17) Testing Suggestions (Future Work)
- Unit tests:
  - `parse_amount` normalization corners (commas, spaces, non-breaking spaces).
  - `fuzzy_match` correctness and thresholds.
  - SWIFT country extraction edge cases.
  - Confidence aggregation determinism.
- Integration tests:
  - End-to-end with small sample Excels.
  - Mock OpenAI and web research.
- Property-based tests for matcher robustness.

## 18) Known Limitations and Improvements
- UI lacks progress polling; relies on manual reload.
- No auth/CSRF; add when exposed beyond a trusted network.
- Output path handling in Docker may need volume mapping for `DESKTOP_PATH`.
- Google scraping is fragile; migrate to a compliant search API.
- Add persistent job queue (Celery+Redis) and replace in-memory dict.
- Add pagination/streaming for very large Excels; parallelize analysis.
- Internationalization of UI; richer result presentation.

## 19) Repository Structure
```
.
├── Dockerfile
├── docker-compose.yml
├── README.md
└── offshore_detector/
    ├── app.py
    ├── offshore_detector.py
    ├── analyzer.py
    ├── ai_classifier.py
    ├── excel_handler.py
    ├── fuzzy_matcher.py
    ├── web_research.py
    ├── config.py
    ├── requirements.txt
    └── templates/
        └── index.html
```

## 20) Compliance and Privacy
- Ensure usage of external services (OpenAI, OSM Nominatim, search) complies with regulatory and vendor terms.
- Do not send sensitive data to third parties without consent and proper data handling agreements.

## 21) Quick Reference
- Main Flask app: `offshore_detector/app.py`
- Orchestrator: `offshore_detector/offshore_detector.py`
- Analyzer: `offshore_detector/analyzer.py`
- AI Classifier: `offshore_detector/ai_classifier.py`
- Excel I/O: `offshore_detector/excel_handler.py`
- Config/env: `offshore_detector/config.py`
- Run: `docker-compose up --build`
