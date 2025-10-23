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

def _normalize_bank_query(name: str) -> str:
    """
    Normalize bank name for geocoding query.
    Extracts the core bank name, removing addresses and noise.
    """
    if not isinstance(name, str):
        return ""
    
    # Normalize line separators
    raw = name.replace("/", " ").replace("\\", " ")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return ""

    # Keyword regex for bank identification
    keyword_re = re.compile(r"\b(bank|банк|банка)\b", re.IGNORECASE)
    
    # Prefer a line containing bank keywords
    candidate = next((ln for ln in lines if keyword_re.search(ln)), None)
    
    # Fallback: pick line with highest alphabetic ratio
    if candidate is None:
        def alpha_ratio(s: str) -> float:
            letters = sum(ch.isalpha() for ch in s)
            return letters / max(1, len(s))
        candidate = max(lines, key=alpha_ratio)

    # Clean up the candidate string
    s = candidate.split(',')[0].strip()  # Cut at first comma
    
    # Remove common address patterns
    address_pattern = r"\b(floor|fl|avenue|ave|road|rd|street|st|bldg|building|no\.?|№|suite|ste|unit)\b.*$"
    s = re.sub(address_pattern, "", s, flags=re.IGNORECASE).strip()
    
    # Remove trailing parentheses if they don't contain bank keywords
    m = re.search(r"\(([^)]*)\)$", s)
    if m and not keyword_re.search(m.group(1)):
        s = re.sub(r"\([^)]*\)$", "", s).strip()
    
    # Clean up extra whitespace and trailing numbers
    s = re.sub(r"\s+\d+$", "", s).strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^[^\w]*", "", s)
    
    # Ensure not empty and limit length
    return s[:100] if s else lines[0][:80]


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

    q = _normalize_bank_query(bank_name)
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
        logging.info("Geocoding request: q='%s'%s", q, 
                    f", countrycodes={params.get('countrycodes')}" if 'countrycodes' in params else "")
        
        response = requests.get(url, params=params, headers=headers, timeout=8)
        response.raise_for_status()
        result = response.json()
        
        # Log compact summary
        _log_geocoding_result(result, bank_name, q, params.get('countrycodes'))
        
        return result
        
    except requests.RequestException as e:
        logging.error(f"Geocoding request failed for '{bank_name}': {e}")
        return None


def _log_geocoding_result(result, bank_name, query, countrycodes):
    """
    Log a compact summary of the geocoding result.
    Separated for better testability and readability.
    """
    try:
        if result and len(result) > 0:
            first = result[0]
            summary = {
                "bank": bank_name[:50],  # Truncate long bank names
                "display_name": first.get("display_name", "")[:100],
                "lat": first.get("lat"),
                "lon": first.get("lon"),
                "query": query,
                "countrycodes": countrycodes
            }
            logging.info("Geocoding summary: %s", json.dumps(summary, ensure_ascii=False))
        else:
            logging.info("Geocoding: No results found for bank='%s'", bank_name[:50])
    except Exception as e:
        logging.debug(f"Failed to log geocoding result: {e}")

def _swift_to_country_code(swift_code: str | None) -> str | None:
    """
    Extract ISO country code from SWIFT/BIC code.
    SWIFT codes are 8 or 11 characters, with country code at positions 4-6.
    """
    if not isinstance(swift_code, str):
        return None
    
    swift_clean = swift_code.strip().upper()
    if len(swift_clean) not in (8, 11):
        return None
    
    country_code = swift_clean[4:6]
    # Validate it's alphabetic
    return country_code if country_code.isalpha() else None


async def run_web_research(counterparty_name, bank_name, swift_code: str | None = None):
    """
    Run async geocoding research for the transaction.
    Returns geocoding results in a standardized format.
    """
    loop = asyncio.get_event_loop()
    
    # Extract country code from SWIFT for targeted geocoding
    country_code = _swift_to_country_code(swift_code)
    
    # Run geocoding in executor to avoid blocking
    geocode_task = loop.run_in_executor(None, geocode_bank, bank_name, country_code)
    geocode_result = await geocode_task
    
    # Log completion with key details
    _log_research_completion(counterparty_name, bank_name, geocode_result)
    
    return {"geocoding": geocode_result, "search_results": None}


def _log_research_completion(counterparty_name, bank_name, geocode_result):
    """Log web research completion with key details."""
    try:
        if geocode_result and len(geocode_result) > 0:
            display_name = geocode_result[0].get("display_name", "Unknown")[:100]
            logging.info("Web research completed: counterparty='%s', bank='%s' -> %s",
                        counterparty_name[:50] if counterparty_name else "N/A",
                        bank_name[:50] if bank_name else "N/A",
                        display_name)
        else:
            logging.info("Web research completed with no results: counterparty='%s', bank='%s'",
                        counterparty_name[:50] if counterparty_name else "N/A",
                        bank_name[:50] if bank_name else "N/A")
    except Exception as e:
        logging.debug(f"Failed to log research completion: {e}")

def parallel_web_research(counterparty_name, bank_name, swift_code: str | None = None):
    """
    Entry point for web research with proper event loop handling.
    Handles both cases: with and without an existing event loop.
    """
    try:
        # Check if there's already a running event loop
        asyncio.get_running_loop()
        # If we get here, there's a running loop - use thread executor
        return _run_in_thread(counterparty_name, bank_name, swift_code)
    except RuntimeError:
        # No running loop, create a new one
        return _run_with_new_loop(counterparty_name, bank_name, swift_code)


def _run_with_new_loop(counterparty_name, bank_name, swift_code):
    """Run web research in a new event loop."""
    try:
        return asyncio.run(run_web_research(counterparty_name, bank_name, swift_code))
    except Exception as e:
        logging.error(f"Error in web research (new loop): {e}", exc_info=True)
        return {"geocoding": None, "search_results": None}


def _run_in_thread(counterparty_name, bank_name, swift_code):
    """Run web research in a separate thread to avoid event loop conflicts."""
    import concurrent.futures
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(
            asyncio.run, 
            run_web_research(counterparty_name, bank_name, swift_code)
        )
        try:
            return future.result(timeout=30)
        except concurrent.futures.TimeoutError:
            logging.error("Web research timed out after 30 seconds")
            return {"geocoding": None, "search_results": None}
        except Exception as e:
            logging.error(f"Error in web research (thread executor): {e}", exc_info=True)
            return {"geocoding": None, "search_results": None}
