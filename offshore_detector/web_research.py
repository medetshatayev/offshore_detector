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
from typing import Optional

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
    Preserves original case to maintain readability of mixed-script text.
    
    Args:
        name: Raw bank name string (may contain mixed Latin/Cyrillic)
    
    Returns:
        Normalized bank name suitable for geocoding (max 100 chars)
    """
    if not isinstance(name, str) or not name.strip():
        return ""
    
    # Remove leading routing/account numbers and slashes
    # Pattern: //RU044525700.30101810200000000700 АО BANK
    # or: //РУ044525700.30101810200000000700 АО BANK (Cyrillic)
    s = name
    # Remove leading slashes and account-like patterns (support both Latin and Cyrillic)
    s = re.sub(r'^[/\\]*\s*[\w]{0,4}\d+[.\d]*\s*', '', s, flags=re.UNICODE)
    
    # Normalize line separators but preserve the text
    s = s.replace("/", " ").replace("\\", " ")
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    
    # Edge case: empty after processing
    if not lines:
        return ""

    # Keyword regex for bank identification (case-insensitive, supports Cyrillic)
    keyword_re = re.compile(r"\b(bank|банк|банка)\b", re.IGNORECASE)
    
    # Prefer a line containing bank keywords
    candidate = next((ln for ln in lines if keyword_re.search(ln)), None)
    
    # Fallback: pick line with highest alphabetic ratio
    if candidate is None:
        def alpha_ratio(s: str) -> float:
            letters = sum(ch.isalpha() for ch in s)
            return letters / max(1, len(s))
        
        # Ensure we have at least one line with some alphabetic content
        lines_with_letters = [ln for ln in lines if any(ch.isalpha() for ch in ln)]
        if lines_with_letters:
            candidate = max(lines_with_letters, key=alpha_ratio)
        else:
            # Last resort: use first line
            candidate = lines[0]

    # Clean up the candidate string
    s = candidate.split(',')[0].strip()  # Cut at first comma
    
    # Remove common address patterns (case-insensitive, supports Cyrillic)
    address_pattern = r"\b(floor|fl|avenue|ave|road|rd|street|st|bldg|building|no\.?|№|suite|ste|unit|этаж|улица|ул)\b.*$"
    s = re.sub(address_pattern, "", s, flags=re.IGNORECASE).strip()
    
    # Remove trailing parentheses if they don't contain bank keywords
    m = re.search(r"\(([^)]*)\)$", s)
    if m and not keyword_re.search(m.group(1)):
        s = re.sub(r"\([^)]*\)$", "", s).strip()
    
    # Clean up extra whitespace and trailing standalone numbers
    s = re.sub(r"\s+\d+$", "", s).strip()
    s = re.sub(r"\s+", " ", s)
    
    # Remove leading non-word characters but preserve Unicode letters
    s = re.sub(r"^[\W_]+", "", s, flags=re.UNICODE).strip()
    
    # Ensure not empty and limit length
    if s:
        return s[:100]
    else:
        # Fallback to first line if all cleaning removed everything
        return lines[0][:80]


def _normalize_cache_key(bank_name, swift_country_code: Optional[str]) -> tuple:
    """
    Normalize arguments for consistent cache keys.
    Returns a tuple of (normalized_bank_name, normalized_country_code).
    
    Note: Does NOT lowercase bank names to preserve mixed-script text (Cyrillic + Latin).
    Only normalizes whitespace for cache consistency.
    """
    # Normalize bank name: strip and collapse whitespace, but preserve case
    norm_bank = " ".join((bank_name or "").split()) if bank_name else ""
    
    # Normalize country code to uppercase and strip (None becomes empty string for caching)
    norm_country = (swift_country_code or "").strip().upper() if swift_country_code else ""
    
    return (norm_bank, norm_country)


@lru_cache(maxsize=500)  # Cache up to 500 unique bank lookups
def _geocode_bank_cached(norm_bank: str, norm_country: str):
    """
    Internal cached geocoding function with normalized arguments.
    """
    if not norm_bank:
        return None
    
    rate_limit('geocode', min_interval=1.0)  # Nominatim requires 1 req/sec max

    q = _normalize_bank_query(norm_bank)
    if not q:
        q = norm_bank[:80]
    
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': q,
        'format': 'json',
        'limit': 2
    }
    # If we have a SWIFT-derived ISO2 country code, constrain the search
    if norm_country and len(norm_country) == 2 and norm_country.isalpha():
        params['countrycodes'] = norm_country.lower()
    headers = {
        'User-Agent': 'OffshoreDetector/1.0 (mshatayev@gmail.com)',
        'Accept': 'application/json'
    }
    try:
        # Log request with query preview
        query_preview = q[:80] if len(q) <= 80 else q[:77] + "..."
        logging.info("Geocoding request: q='%s'%s", query_preview,
                    f", countrycodes={params.get('countrycodes')}" if 'countrycodes' in params else "")
        
        response = requests.get(url, params=params, headers=headers, timeout=8)
        response.raise_for_status()
        result = response.json()
        
        # Log compact summary (use normalized bank name for logging)
        _log_geocoding_result(result, norm_bank, query_preview, params.get('countrycodes'))
        
        return result
        
    except requests.RequestException as e:
        # Truncate error message to prevent log spam
        bank_preview = norm_bank[:80] if len(norm_bank) <= 80 else norm_bank[:77] + "..."
        logging.error(f"Geocoding request failed for '{bank_preview}': {e}")
        return None


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
def geocode_bank(bank_name, swift_country_code: Optional[str] = None):
    """
    Geocode bank name using OpenStreetMap Nominatim.
    Performance: Cached to avoid redundant API calls. Rate-limited to respect API usage policies.
    
    Args:
        bank_name: Name of the bank to geocode
        swift_country_code: Optional ISO country code from SWIFT (will be normalized)
    
    Returns:
        List of geocoding results or None
    """
    # Normalize arguments for consistent caching
    norm_bank, norm_country = _normalize_cache_key(bank_name, swift_country_code)
    
    if not norm_bank:
        return None
    
    # Call cached internal function with normalized arguments
    return _geocode_bank_cached(norm_bank, norm_country)


def _log_geocoding_result(result, bank_name, query, countrycodes):
    """
    Log a compact summary of the geocoding result.
    Separated for better testability and readability.
    Note: Logs may contain PII (bank names). Consider masking in production.
    """
    try:
        # Truncate bank name for logging (prevent log spam)
        bank_display = bank_name[:80] if len(bank_name) <= 80 else bank_name[:77] + "..."
        
        if result and len(result) > 0:
            first = result[0]
            summary = {
                "bank": bank_display,
                "display_name": first.get("display_name", "")[:100],
                "lat": first.get("lat"),
                "lon": first.get("lon"),
                "query": query,  # Already truncated in caller
                "countrycodes": countrycodes
            }
            logging.info("Geocoding summary: %s", json.dumps(summary, ensure_ascii=False))
        else:
            logging.info("Geocoding: No results for query='%s' (bank='%s')", query, bank_display)
    except Exception as e:
        logging.debug(f"Failed to log geocoding result: {e}")

def _swift_to_country_code(swift_code: Optional[str]) -> Optional[str]:
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


async def run_web_research(counterparty_name, bank_name, swift_code: Optional[str] = None):
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
    """
    Log web research completion with key details.
    Note: Logs may contain PII. Consider masking counterparty/bank names in production.
    """
    try:
        # Mask or truncate PII
        cp_display = counterparty_name[:50] if counterparty_name else "N/A"
        bank_display = bank_name[:50] if bank_name else "N/A"
        
        if geocode_result and len(geocode_result) > 0:
            display_name = geocode_result[0].get("display_name", "Unknown")[:100]
            logging.info("Web research completed: counterparty='%s', bank='%s' -> %s",
                        cp_display, bank_display, display_name)
        else:
            logging.info("Web research completed with no results: counterparty='%s', bank='%s'",
                        cp_display, bank_display)
    except Exception as e:
        logging.debug(f"Failed to log research completion: {e}")

def parallel_web_research(counterparty_name, bank_name, swift_code: Optional[str] = None):
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
