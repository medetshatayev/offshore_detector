"""
Geo search (OpenStreetMap Nominatim)
Logs geocoding responses for observability.
"""
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio
import logging
from functools import lru_cache
import time
import threading
import json

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
def geocode_bank(bank_name):
    """
    Geocode bank name using OpenStreetMap Nominatim.
    Performance: Cached to avoid redundant API calls. Rate-limited to respect API usage policies.
    """
    if not bank_name:
        return None
    
    rate_limit('geocode', min_interval=1.0)  # Nominatim requires 1 req/sec max
    
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': bank_name[:100],
        'format': 'json',
        'limit': 1
    }
    headers = {
        'User-Agent': 'OffshoreDetector/1.0 (mshatayev@gmail.com)',
        'Accept': 'application/json'
    }
    try:
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

async def run_web_research(counterparty_name, bank_name):
    """
    Run geocoding
    """
    loop = asyncio.get_event_loop()
    
    geocode_task = loop.run_in_executor(None, geocode_bank, bank_name)
    geocode_result = await geocode_task
    try:
        first = (geocode_result or [None])[0] or {}
        logging.info("Web research completed for counterparty='%s', bank='%s' -> display_name='%s'", counterparty_name, bank_name, first.get("display_name"))
    except Exception:
        pass
    return {"geocoding": geocode_result, "search_results": None}

def parallel_web_research(counterparty_name, bank_name):
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
            return asyncio.run(run_web_research(counterparty_name, bank_name))
        except Exception as e:
            logging.error(f"Error in web research: {e}")
            return {"geocoding": None, "search_results": None}
    else:
        # Loop is already running, use run_in_executor
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, run_web_research(counterparty_name, bank_name))
            try:
                return future.result(timeout=30)
            except Exception as e:
                logging.error(f"Error in web research: {e}")
                return {"geocoding": None, "search_results": None}
