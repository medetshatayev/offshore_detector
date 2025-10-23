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
    SIMPLIFIED STRATEGY: Extract bank name + city only.
    
    Geocoding APIs work best with simple queries like:
    - "HSBC Hong Kong" ✓
    - "Raiffeisenbank Moscow" ✓
    NOT:
    - "HONGKONG AND SHANGHAI BANKING CORPORATION LIMITED, THE ALL HK OFFICES..." ✗
    
    Args:
        name: Raw bank name string (may contain mixed Latin/Cyrillic)
    
    Returns:
        Simplified query: "BankName City" (max 100 chars)
    """
    if not isinstance(name, str) or not name.strip():
        return ""
    
    # Remove leading routing/account numbers and slashes
    s = name
    s = re.sub(r'^[/\\]*\s*[\w]{0,4}\d+[.\d]*\s*', '', s, flags=re.UNICODE)
    
    # Normalize line separators
    s = s.replace("/", " ").replace("\\", " ")
    s = re.sub(r"\s+", " ", s).strip()
    
    if not s:
        return ""
    
    # Common city/country names to extract  
    known_locations = {
        'moscow': 'Moscow', 'москва': 'Moscow', 'moskva': 'Moscow',
        'istanbul': 'Istanbul', 'стамбул': 'Istanbul',
        'kiev': 'Kiev', 'киев': 'Kiev', 'kyiv': 'Kyiv',
        'hong kong': 'Hong Kong', 'гонконг': 'Hong Kong', 'hongkon': 'Hong Kong',
        'seoul': 'Seoul', 'сеул': 'Seoul',
        'miami': 'Miami', 'майами': 'Miami',
        'ankara': 'Ankara', 'анкара': 'Ankara',
        'almaty': 'Almaty', 'алматы': 'Almaty',
        'astana': 'Astana', 'астана': 'Astana',
        'coral gables': 'Coral Gables',
        'turkey': 'Turkey', 'ukraine': 'Ukraine', 'korea': 'Korea',
        'philippines': 'Manila', 'manila': 'Manila'
    }
    
    # Well-known bank name mappings (bank_key: (standard_name, home_city))
    # Helps geocoding by providing bank's known home location
    bank_aliases = {
        'hongkong shanghai': ('HSBC', 'Hong Kong'),
        'hongkong and shanghai': ('HSBC', 'Hong Kong'),
        'hsbc': ('HSBC', 'Hong Kong'),
        'dbs': ('DBS', None),
        'raiffeisen': ('Raiffeisenbank', None),
        'райффайзен': ('Raiffeisenbank', None),
        'vakiflar': ('Vakifbank', None),
        'metropolitan bank and trust': ('Metrobank', 'Manila'),  # Filipino bank
        'banco pichincha': ('Banco Pichincha', 'Miami'),  # Miami branch is common
        'bank of america': ('Bank of America', None),
        'bank america': ('Bank of America', None)
    }
    
    # Remove detailed address components
    s = re.sub(r'\b(room|office|floor|fl|penthouse|building|suite|ste|unit)\s+[\w\d-]+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\b(no\.?|№)\s*\d+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\b\d+[/-]\d+\b', '', s)  # Remove "42/4", "61-65"
    # Remove street addresses but NOT everything after (to preserve city names)
    s = re.sub(r'\b\d+\s+(street|st|road|rd|avenue|ave|boulevard|blvd|caddesi|ulitsa|circle|square|drive|dr)\b', '', s, flags=re.IGNORECASE)
    # Remove "BUYUKDERE CADDESI" type patterns (street name + type)
    s = re.sub(r'\b\w+\s+(street|st|road|rd|avenue|ave|boulevard|blvd|caddesi|ulitsa|circle|square|drive|dr)\b', '', s, flags=re.IGNORECASE)
    
    # Remove fragments like "STATES" from "UNITED STATES"
    s = re.sub(r'\bSTATES\b', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\bUNITED\b', '', s, flags=re.IGNORECASE)
    
    # Clean up
    s = re.sub(r'\s+', ' ', s).strip()
    
    # Extract city/location
    location = None
    s_lower = s.lower()
    # Check for multi-word locations first (like "hong kong", "coral gables")
    for loc_key in sorted(known_locations.keys(), key=len, reverse=True):
        if loc_key in s_lower:
            location = known_locations[loc_key]
            # Remove the location from string to avoid duplication
            s = re.sub(re.escape(loc_key), '', s, flags=re.IGNORECASE)
            break
    
    # Clean up after location removal
    s = re.sub(r'\s+', ' ', s).strip()
    
    # Check for well-known bank aliases first
    s_lower = s.lower()
    bank_name = None
    bank_home_location = None
    for alias, (standard_name, home_city) in bank_aliases.items():
        if alias in s_lower:
            bank_name = standard_name
            bank_home_location = home_city
            break
    
    # If no alias matched, extract bank name from words
    if not bank_name:
        words = s.split()
        stopwords = {'the', 'all', 'and', 'of', 'a', 'an', 'limited', 'ltd', 'corporation', 'corp', 'n.a.', 'agency', 'department', 'treasury', 'head', 'offices', 'office', 'jsc', 'a.s.', 'plaza', 'center', 'central', 't.a.o.', 't.a.o', 'tao'}
        meaningful_words = [w for w in words if w.lower() not in stopwords and len(w) > 1 and not w.isdigit()]
        
        # Take first 2-3 meaningful words for bank name (shorter is better)
        bank_name_words = meaningful_words[:3]
        bank_name = ' '.join(bank_name_words)
    
    # Construct simple query: "BankName Location"
    # Prefer bank's home location if known
    final_location = bank_home_location if bank_home_location else location
    
    if final_location and bank_name:
        query = f"{bank_name} {final_location}"
    elif bank_name:
        query = bank_name
    elif final_location:
        query = final_location
    else:
        # Fallback: use original cleaned string
        query = s[:50]
    
    # Final cleanup
    query = re.sub(r'\s+', ' ', query).strip()
    query = re.sub(r'[,;()]+', '', query)  # Remove extra punctuation
    query = re.sub(r'\s+', ' ', query).strip()
    
    return query[:100]


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
