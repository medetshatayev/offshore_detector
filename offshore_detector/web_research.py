"""
Geo search (OpenStreetMap Nominatim)
Logs geocoding responses for observability and normalizes bank query.
"""
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio
import logging
from functools import lru_cache
import time
import threading
import json
import re

# Simple cache for search results (since they return lists which are not hashable)
_search_cache = {}

# Rate limiting: Track last request time
_last_request_time = {'geocode': 0.0}
_rate_limit_lock = threading.Lock()

def rate_limit(service, min_interval=1.0):
    """
    Simple rate limiter to avoid overwhelming external APIs.
    """
    with _rate_limit_lock:
        elapsed = time.time() - _last_request_time.get(service, 0.0)
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time[service] = time.time()

@lru_cache(maxsize=500)  # Cache up to 500 unique bank lookups
@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
def geocode_bank(bank_name, swift_country_code: str | None = None):
    """
    Geocode bank name using OpenStreetMap Nominatim.
    Performance: Cached to avoid redundant API calls. Rate-limited to respect API usage policies.
    """
    if not bank_name:
        return None
    
    rate_limit('geocode', min_interval=1.0)  # Nominatim requires 1 req/sec max

    # Normalize bank query: choose best line, keep core bank name, drop addresses/noise
    def normalize_bank_query(name: str) -> str:
        if not isinstance(name, str):
            return ""
        raw = name.replace("/", " ").replace("\\", " ")
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if not lines:
            return ""

        # Prefer a line containing keywords
        keyword_re = re.compile(r"\b(bank|банк|банка)\b", re.IGNORECASE)
        candidate = next((ln for ln in lines if keyword_re.search(ln)), None)
        if candidate is None:
            # Fallback: pick line with highest alphabetic ratio
            def alpha_ratio(s: str) -> float:
                letters = sum(ch.isalpha() for ch in s)
                return letters / max(1, len(s))
            candidate = max(lines, key=alpha_ratio)

        s = candidate
        # Cut at first comma
        s = s.split(',')[0].strip()
        # Remove common address tails
        s = re.sub(r"\b(floor|fl|avenue|ave|road|rd|street|st|bldg|building|no\.?|№|suite|ste|unit)\b.*$", "", s, flags=re.IGNORECASE).strip()
        # Remove trailing parentheses content if looks like address, keep if contains 'bank/банк'
        m = re.search(r"\(([^)]*)\)$", s)
        if m and not keyword_re.search(m.group(1)):
            s = re.sub(r"\([^)]*\)$", "", s).strip()
        # Remove trailing standalone numbers
        s = re.sub(r"\s+\d+$", "", s).strip()
        # Collapse spaces and leading non-letters/punct
        s = re.sub(r"\s+", " ", s)
        s = re.sub(r"^[^\w]*", "", s)
        # Ensure not empty and limit length
        if not s:
            s = lines[0][:80]
        return s[:100]

    q = normalize_bank_query(bank_name)
    if not q:
        q = (bank_name or "")[:80]
    
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': q,
        'format': 'json',
        'limit': 2
    }
    # If we have a SWIFT-derived ISO2 country code, constrain the search
    if isinstance(swift_country_code, str) and len(swift_country_code) == 2 and swift_country_code.isalpha():
        params['countrycodes'] = swift_country_code.lower()
    headers = {
        'User-Agent': 'OffshoreDetector/1.0 (mshatayev@gmail.com)',
        'Accept': 'application/json'
    }
    try:
        logging.info("Geocoding request: q='%s'%s", q, f", countrycodes={params.get('countrycodes')}" if 'countrycodes' in params else "")
        response = requests.get(url, params=params, headers=headers, timeout=8)
        response.raise_for_status()
        result = response.json()
        # Derive compact summary if available
        try:
            first = (result or [None])[0] or {}
            summary = {
                "bank": bank_name,
                "display_name": first.get("display_name"),
                "lat": first.get("lat"),
                "lon": first.get("lon"),
                "status": response.status_code,
                "query": q,
                "countrycodes": params.get('countrycodes')
            }
            logging.info("Geocoding summary: %s", json.dumps(summary, ensure_ascii=False))
        except Exception:
            # Fallback to truncated payload
            try:
                snippet = json.dumps(result, ensure_ascii=False)[:800]
                logging.info("Geocoding response (truncated) for bank='%s': %s%s", bank_name, snippet, "..." if len(snippet) == 800 else "")
            except Exception:
                logging.info("Geocoding response received for bank='%s' (serialization skipped)", bank_name)
        return result
    except requests.RequestException as e:
        logging.error(f"Geocoding request failed: {e}")
        return None

def _swift_to_country_code(swift_code: str | None) -> str | None:
    if not isinstance(swift_code, str):
        return None
    s = swift_code.strip().upper()
    if len(s) not in (8, 11):
        return None
    return s[4:6]

async def run_web_research(counterparty_name, bank_name, swift_code: str | None = None):
    """
    Run geocoding
    """
    loop = asyncio.get_event_loop()
    
    country_code = _swift_to_country_code(swift_code)
    geocode_task = loop.run_in_executor(None, geocode_bank, bank_name, country_code)
    geocode_result = await geocode_task
    try:
        first = (geocode_result or [None])[0] or {}
        logging.info("Web research completed for counterparty='%s', bank='%s' -> display_name='%s'", counterparty_name, bank_name, first.get("display_name"))
    except Exception:
        pass
    return {"geocoding": geocode_result, "search_results": None}

def parallel_web_research(counterparty_name, bank_name, swift_code: str | None = None):
    """
    Entry point for web research.
    Proper event loop handling for all contexts.
    """
    try:
        # Try to get the running loop
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, create a new one
        try:
            return asyncio.run(run_web_research(counterparty_name, bank_name, swift_code))
        except Exception as e:
            logging.error(f"Error in web research: {e}")
            return {"geocoding": None, "search_results": None}
    else:
        # Loop is already running, use run_in_executor
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, run_web_research(counterparty_name, bank_name, swift_code))
            try:
                return future.result(timeout=30)
            except Exception as e:
                logging.error(f"Error in web research: {e}")
                return {"geocoding": None, "search_results": None}
